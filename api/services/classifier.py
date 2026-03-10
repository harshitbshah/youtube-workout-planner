"""
api/services/classifier.py — Classify unclassified videos using Anthropic Batch API.

Reuses pure functions from src/classifier.py (prompt building, response parsing,
transcript fetching). Only the DB layer is rewritten to use SQLAlchemy.

Platform-pays model for v1: uses server-side ANTHROPIC_API_KEY.
"""

import logging
import os
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.classifier import (
    BATCH_POLL_INTERVAL,
    MODEL,
    SYSTEM_PROMPT,
    _build_user_message,
    _fetch_transcript_intro,
    _parse_classification,
)

from ..models import Channel, Classification, Video

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


# ─── DB helpers ───────────────────────────────────────────────────────────────

def _fetch_unclassified_for_user(session: Session, user_id: str) -> list[dict]:
    """Return unclassified videos (≥3 min) belonging to this user's channels."""
    rows = (
        session.query(Video)
        .join(Channel, Channel.id == Video.channel_id)
        .outerjoin(Classification, Classification.video_id == Video.id)
        .filter(
            Channel.user_id == user_id,
            Classification.video_id.is_(None),
            Video.duration_sec >= 180,
        )
        .order_by(Video.published_at.desc())
        .all()
    )
    return [
        {
            "id": v.id,
            "title": v.title,
            "description": v.description,
            "duration_sec": v.duration_sec,
            "tags": v.tags,
        }
        for v in rows
    ]


def _save_classification(session: Session, video_id: str, classification: dict):
    existing = session.get(Classification, video_id)
    if existing:
        existing.workout_type = classification["workout_type"]
        existing.body_focus = classification["body_focus"]
        existing.difficulty = classification["difficulty"]
        existing.has_warmup = bool(classification["has_warmup"])
        existing.has_cooldown = bool(classification["has_cooldown"])
        existing.classified_at = datetime.now(timezone.utc).isoformat()
    else:
        session.add(Classification(
            video_id=video_id,
            workout_type=classification["workout_type"],
            body_focus=classification["body_focus"],
            difficulty=classification["difficulty"],
            has_warmup=bool(classification["has_warmup"]),
            has_cooldown=bool(classification["has_cooldown"]),
            classified_at=datetime.now(timezone.utc).isoformat(),
        ))
    session.commit()


# ─── Public API ───────────────────────────────────────────────────────────────

# Max videos to classify in a single pipeline run. Keeps the batch small enough
# to complete in a reasonable time. Unclassified videos beyond this cap will be
# picked up on the next scan (incremental runs classify newly added videos only).
MAX_CLASSIFY_PER_RUN = 300


def _get_or_create_credentials(session: Session, user_id: str):
    """Return UserCredentials for user, creating a blank row if none exists."""
    from ..models import UserCredentials
    creds = session.get(UserCredentials, user_id)
    if not creds:
        creds = UserCredentials(user_id=user_id)
        session.add(creds)
        session.commit()
    return creds


def _save_batch_id(session: Session, user_id: str, batch_id: str | None):
    creds = _get_or_create_credentials(session, user_id)
    creds.classifier_batch_id = batch_id
    session.commit()


def _save_results(session: Session, user_id: str, client, batch) -> tuple[int, int, int, int]:
    """Iterate batch results and save classifications.
    Returns (classified, failed, input_tokens, output_tokens)."""
    classified = 0
    failed = 0
    input_tokens = 0
    output_tokens = 0
    for result in client.messages.batches.results(batch.id):
        if result.result.type == "succeeded":
            # Skip if the video was deleted after the batch was submitted
            if not session.get(Video, result.custom_id):
                logger.info(f"[user={user_id}] Skipping {result.custom_id} — video no longer in DB")
                continue
            raw = result.result.message.content[0].text
            clf = _parse_classification(raw)
            if clf:
                _save_classification(session, result.custom_id, clf)
                classified += 1
                usage = result.result.message.usage
                input_tokens += getattr(usage, "input_tokens", 0) or 0
                output_tokens += getattr(usage, "output_tokens", 0) or 0
            else:
                failed += 1
        else:
            logger.warning(f"[user={user_id}] Failed: {result.custom_id} — {result.result.type}")
            failed += 1
    return classified, failed, input_tokens, output_tokens


def classify_for_user(session: Session, user_id: str, api_key: str = "", on_progress=None) -> int:
    """
    Classify unclassified videos for a user's channels using Anthropic Batch API.

    Resumable: if a batch was previously submitted (batch ID persisted in DB),
    resumes polling or retrieves results directly — no resubmission or double billing.
    Processes up to MAX_CLASSIFY_PER_RUN videos per call; remainder deferred to next run.

    Returns count of successfully classified videos.
    """
    import anthropic

    key = api_key or ANTHROPIC_API_KEY
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    client = anthropic.Anthropic(api_key=key)

    # ── Resume: check for an existing batch from a previous interrupted run ──
    creds = _get_or_create_credentials(session, user_id)
    if creds.classifier_batch_id:
        batch_id = creds.classifier_batch_id
        logger.info(f"[user={user_id}] Found existing batch {batch_id} — checking status...")
        try:
            batch = client.messages.batches.retrieve(batch_id)
            counts = batch.request_counts
            total = counts.succeeded + counts.errored + counts.canceled + counts.expired + counts.processing
            if batch.processing_status != "ended":
                logger.info(f"[user={user_id}] Batch still processing — resuming poll")
            else:
                logger.info(f"[user={user_id}] Batch already ended — retrieving results directly")
            # Fall through to Phase 3 (poll/retrieve results)
        except Exception as e:
            logger.warning(f"[user={user_id}] Could not retrieve batch {batch_id}: {e} — submitting new batch")
            _save_batch_id(session, user_id, None)
            batch = None
            total = 0
    else:
        batch = None
        total = 0

    if batch is None:
        # ── Phase 1: build batch requests ────────────────────────────────────
        all_videos = _fetch_unclassified_for_user(session, user_id)
        if not all_videos:
            logger.info(f"[user={user_id}] No unclassified videos.")
            return 0

        videos = all_videos[:MAX_CLASSIFY_PER_RUN]
        total = len(videos)
        skipped = len(all_videos) - total
        if skipped:
            logger.info(f"[user={user_id}] {len(all_videos)} unclassified — processing first {total}, {skipped} deferred")

        logger.info(f"[user={user_id}] Building {total} classification requests...")
        requests = []
        for i, video in enumerate(videos):
            transcript_intro = _fetch_transcript_intro(video["id"])
            user_message = _build_user_message(video, transcript_intro)
            requests.append({
                "custom_id": video["id"],
                "params": {
                    "model": MODEL,
                    "max_tokens": 150,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_message}],
                },
            })
            if on_progress and (i + 1) % 10 == 0:
                on_progress(total, -(i + 1))  # negative = still building

        # ── Phase 2: submit batch + persist ID immediately ────────────────────
        logger.info(f"[user={user_id}] Submitting batch of {total} to Anthropic...")
        batch = client.messages.batches.create(requests=requests)
        _save_batch_id(session, user_id, batch.id)
        logger.info(f"[user={user_id}] Batch submitted — ID: {batch.id}")

    # ── Phase 3: poll until complete ──────────────────────────────────────────
    while batch.processing_status != "ended":
        time.sleep(BATCH_POLL_INTERVAL)
        batch = client.messages.batches.retrieve(batch.id)
        counts = batch.request_counts
        done = counts.succeeded + counts.errored + counts.canceled + counts.expired
        logger.info(f"[user={user_id}] {batch.id}: {done}/{total} done")
        if on_progress:
            on_progress(total, done)

    # Emit final progress (covers the case where batch was already ended on first check)
    if on_progress:
        counts = batch.request_counts
        done = counts.succeeded + counts.errored + counts.canceled + counts.expired
        on_progress(total, done)

    # ── Phase 4: save results + clear batch ID + record usage ─────────────────
    classified, failed, input_tokens, output_tokens = _save_results(session, user_id, client, batch)
    _save_batch_id(session, user_id, None)

    try:
        from ..models import BatchUsageLog
        session.add(BatchUsageLog(
            user_id=user_id,
            batch_id=batch.id,
            videos_submitted=total,
            classified=classified,
            failed=failed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ))
        session.commit()
    except Exception as e:
        logger.warning(f"[user={user_id}] Failed to record batch usage: {e}")

    logger.info(f"[user={user_id}] Done: {classified}/{total} classified, {failed} failed")
    return classified
