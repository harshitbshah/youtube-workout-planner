"""
api/services/classifier.py — Classify unclassified videos using Anthropic Batch API.

Reuses pure functions from src/classifier.py (prompt building, response parsing,
transcript fetching). Only the DB layer is rewritten to use SQLAlchemy.

Platform-pays model for v1: uses server-side ANTHROPIC_API_KEY.
"""

import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.classifier import (
    BATCH_POLL_INTERVAL,
    MODEL,
    SYSTEM_PROMPT,
    _build_user_message,
    _fetch_transcript_intro,
    _parse_classification,
)

from sqlalchemy import or_

from ..models import Channel, Classification, UserChannel, Video

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


# ─── F5: Adaptive payload trimming ────────────────────────────────────────────

_DESCRIPTIVE_PATTERN = re.compile(
    r"\b(\d+\s*(?:min|minute)s?|beginner|advanced|intermediate|hiit|strength|"
    r"cardio|yoga|pilates|mobility|stretching|full[- ]?body|upper[- ]?body|"
    r"lower[- ]?body|core|abs|glutes|legs|arms|chest|back)\b",
    re.IGNORECASE,
)


def _title_is_descriptive(title: str) -> bool:
    """Return True if the title contains enough fitness keywords to classify without transcript."""
    return bool(_DESCRIPTIVE_PATTERN.search(title))


# ─── F6: Rule-based title pre-classifier ──────────────────────────────────────

_TYPE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(hiit|interval)\b", re.I), "HIIT"),
    (re.compile(r"\b(yoga|stretch(?:ing)?|mobility|flexibility|pilates)\b", re.I), "Mobility"),
    (re.compile(r"\b(strength|weight(?:s)?|dumbbell|barbell|resistance|lifting|weight\s*train)\b", re.I), "Strength"),
    (re.compile(r"\b(cardio|run(?:ning)?|cycling|bike|treadmill)\b", re.I), "Cardio"),
]

_FOCUS_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bfull[- ]?body\b", re.I), "full"),
    (re.compile(r"\bupper[- ]?body\b|(?:^|\b)(arms|chest|back|shoulders)\b", re.I), "upper"),
    (re.compile(r"\blower[- ]?body\b|(?:^|\b)(legs|glutes|hamstrings|quads|hips)\b", re.I), "lower"),
    (re.compile(r"\b(core|abs|abdominal)\b", re.I), "core"),
]

_DIFFICULTY_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bbeginner\b", re.I), "beginner"),
    (re.compile(r"\badvanced\b", re.I), "advanced"),
]


def title_classify(title: str, duration_sec: int | None) -> dict | None:
    """
    Attempt rule-based classification from the video title alone.

    Returns a classification dict if a workout type can be determined with
    confidence, else None (caller should fall through to AI classification).
    """
    workout_type = None
    for pattern, wtype in _TYPE_RULES:
        if pattern.search(title):
            workout_type = wtype
            break

    if workout_type is None:
        return None

    body_focus = "full"  # sensible default when type is matched
    for pattern, focus in _FOCUS_RULES:
        if pattern.search(title):
            body_focus = focus
            break

    difficulty = "intermediate"
    for pattern, diff in _DIFFICULTY_RULES:
        if pattern.search(title):
            difficulty = diff
            break

    has_warmup = bool(re.search(r"\bwarm[- ]?up\b", title, re.I))
    has_cooldown = bool(re.search(r"\bcool[- ]?down\b", title, re.I))

    return {
        "workout_type": workout_type,
        "body_focus": body_focus,
        "difficulty": difficulty,
        "has_warmup": has_warmup,
        "has_cooldown": has_cooldown,
    }


# ─── DB helpers ───────────────────────────────────────────────────────────────

def _fetch_unclassified_for_user(session: Session, user_id: str) -> list[dict]:
    """Return unclassified videos (≥3 min, within cutoff age) belonging to this user's channels."""
    max_age_months = int(os.getenv("CLASSIFY_MAX_AGE_MONTHS", "18"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_months * 30)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = (
        session.query(Video)
        .join(Channel, Channel.id == Video.channel_id)
        .join(UserChannel, (UserChannel.channel_id == Channel.id) & (UserChannel.user_id == user_id))
        .outerjoin(Classification, Classification.video_id == Video.id)
        .filter(
            Classification.video_id.is_(None),
            Video.duration_sec >= 180,
            # Include videos with NULL published_at (unknown age — better to classify than skip)
            or_(Video.published_at.is_(None), Video.published_at >= cutoff_str),
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

# Keyword patterns for matching unclassified video titles against gap workout types.
# Used by build_targeted_batch to prioritise videos most likely to fill plan gaps.
TARGETED_BATCH_MULTIPLIER = int(os.getenv("TARGETED_BATCH_MULTIPLIER", "5"))

_GAP_TYPE_PATTERNS: dict[str, re.Pattern] = {
    "hiit":     re.compile(r"\b(hiit|interval|tabata)\b", re.I),
    "strength": re.compile(r"\b(strength|weight|dumbbell|barbell|resistance|lifting)\b", re.I),
    "cardio":   re.compile(r"\b(cardio|run(?:ning)?|cycling|bike|treadmill)\b", re.I),
    "mobility": re.compile(r"\b(yoga|stretch(?:ing)?|mobility|flexibility|pilates)\b", re.I),
}


def rule_classify_for_user(session: Session, user_id: str) -> int:
    """
    Run rule-based classification on all unclassified videos for a user.
    Free — no Anthropic API calls. Returns count of videos classified.
    """
    videos = _fetch_unclassified_for_user(session, user_id)
    classified = 0
    for video in videos:
        result = title_classify(video["title"], video["duration_sec"])
        if result:
            _save_classification(session, video["id"], result)
            classified += 1
    if classified:
        logger.info(f"[user={user_id}] {classified} videos rule-classified")
    return classified


def build_targeted_batch(
    user_id: str,
    gap_types: list[dict],
    session: Session,
) -> tuple[list[dict], list[dict]]:
    """
    Split unclassified videos into (targeted, remainder).
    Targeted = videos whose titles match the missing workout types, capped at
    max(len(gap_types) * TARGETED_BATCH_MULTIPLIER, 10).
    Remainder = everything else, deferred to background classification.
    """
    unclassified = _fetch_unclassified_for_user(session, user_id)
    gap_type_names = {g["workout_type"].lower() for g in gap_types}
    cap = max(len(gap_types) * TARGETED_BATCH_MULTIPLIER, 10)

    targeted: list[dict] = []
    remainder: list[dict] = []
    for video in unclassified:
        title = video["title"]
        matched = any(
            t in gap_type_names and pattern.search(title)
            for t, pattern in _GAP_TYPE_PATTERNS.items()
        )
        if matched and len(targeted) < cap:
            targeted.append(video)
        else:
            remainder.append(video)

    logger.info(
        f"[user={user_id}] Targeted batch: {len(targeted)} for gaps {gap_type_names}, "
        f"{len(remainder)} deferred to background"
    )
    return targeted, remainder


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


def classify_for_user(
    session: Session,
    user_id: str,
    api_key: str = "",
    on_progress=None,
    preselected_videos: list[dict] | None = None,
) -> int:
    """
    Classify unclassified videos for a user's channels using Anthropic Batch API.

    Resumable: if a batch was previously submitted (batch ID persisted in DB),
    resumes polling or retrieves results directly — no resubmission or double billing.
    Processes up to MAX_CLASSIFY_PER_RUN videos per call; remainder deferred to next run.

    preselected_videos: if provided, classify only this specific list (targeted batch).
      Caller is responsible for running rule_classify_for_user first. Rule-based step
      is skipped. If None (default), fetches all unclassified videos and runs rule-based
      pre-classification before submitting to Anthropic.

    Returns count of successfully classified videos.
    """
    import anthropic

    key = api_key or ANTHROPIC_API_KEY
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    client = anthropic.Anthropic(api_key=key)

    rule_classified = 0  # videos classified by rules before batch submission

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
        if preselected_videos is None:
            # Default path: fetch all unclassified + run rule-based pre-classifier
            all_videos = _fetch_unclassified_for_user(session, user_id)
            if not all_videos:
                logger.info(f"[user={user_id}] No unclassified videos.")
                return 0

            # F6: rule-based pre-classification — saves AI calls for obvious titles
            to_classify = []
            for video in all_videos:
                result = title_classify(video["title"], video["duration_sec"])
                if result:
                    _save_classification(session, video["id"], result)
                    rule_classified += 1
                else:
                    to_classify.append(video)

            if rule_classified:
                logger.info(f"[user={user_id}] {rule_classified} rule-classified, {len(to_classify)} sent to AI")

            if not to_classify:
                logger.info(f"[user={user_id}] All videos classified by rules — no AI batch needed")
                return rule_classified
        else:
            # Targeted path: caller already ran rule_classify_for_user and selected
            # only the videos needed to fill plan gaps. Skip fetch and rule-based step.
            to_classify = preselected_videos
            if not to_classify:
                logger.info(f"[user={user_id}] No targeted videos to classify.")
                return 0

        # Cap AI batch
        videos = to_classify[:MAX_CLASSIFY_PER_RUN]
        total = len(videos)
        deferred = len(to_classify) - total
        if deferred:
            logger.info(f"[user={user_id}] {len(to_classify)} for AI — processing first {total}, {deferred} deferred")

        logger.info(f"[user={user_id}] Building {total} classification requests...")
        requests = []
        for i, video in enumerate(videos):
            # F5: skip transcript fetch and trim description for descriptive titles
            if _title_is_descriptive(video["title"]):
                transcript_intro = None
                video_for_msg = {**video, "description": (video.get("description") or "")[:300]}
            else:
                transcript_intro = _fetch_transcript_intro(video["id"])
                video_for_msg = video

            user_message = _build_user_message(video_for_msg, transcript_intro)
            requests.append({
                "custom_id": video["id"],
                "params": {
                    "model": MODEL,
                    "max_tokens": 80,  # JSON response is ~50-70 tokens; 80 gives headroom without waste
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

    total_classified = classified + rule_classified
    logger.info(
        f"[user={user_id}] Done: {total_classified} classified "
        f"({rule_classified} by rules, {classified} by AI), {failed} failed"
    )
    return total_classified
