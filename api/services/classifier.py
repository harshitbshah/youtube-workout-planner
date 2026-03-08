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

def classify_for_user(session: Session, user_id: str, api_key: str = "") -> int:
    """
    Classify all unclassified videos for a user's channels using Anthropic Batch API.
    Returns count of successfully classified videos.
    """
    import anthropic

    key = api_key or ANTHROPIC_API_KEY
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    videos = _fetch_unclassified_for_user(session, user_id)
    total = len(videos)
    if total == 0:
        logger.info(f"[user={user_id}] No unclassified videos.")
        return 0

    client = anthropic.Anthropic(api_key=key)

    # Phase 1: build batch requests
    logger.info(f"[user={user_id}] Building {total} classification requests...")
    requests = []
    for video in videos:
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

    # Phase 2: submit batch
    logger.info(f"[user={user_id}] Submitting batch of {total} to Anthropic...")
    batch = client.messages.batches.create(requests=requests)
    logger.info(f"[user={user_id}] Batch submitted — ID: {batch.id}")

    # Phase 3: poll until complete
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        counts = batch.request_counts
        done = counts.succeeded + counts.errored + counts.canceled + counts.expired
        logger.info(f"[user={user_id}] {batch.id}: {done}/{total} done")
        if batch.processing_status == "ended":
            break
        time.sleep(BATCH_POLL_INTERVAL)

    # Phase 4: save results
    classified = 0
    failed = 0
    for result in client.messages.batches.results(batch.id):
        if result.result.type == "succeeded":
            raw = result.result.message.content[0].text
            clf = _parse_classification(raw)
            if clf:
                _save_classification(session, result.custom_id, clf)
                classified += 1
            else:
                failed += 1
        else:
            logger.warning(f"[user={user_id}] Failed: {result.custom_id} — {result.result.type}")
            failed += 1

    logger.info(f"[user={user_id}] Done: {classified}/{total} classified, {failed} failed")
    return classified
