"""
classifier.py - Classify workout videos using Claude API.

For each unclassified video:
  1. Build context: title + description snippet + transcript intro (first ~2 min)
  2. Submit all videos to Anthropic's Batch API in one request (50% cheaper, faster)
  3. Poll until the batch completes
  4. Parse JSON responses and store results in the classifications table

Uses claude-haiku for cost efficiency - classification is a structured,
well-defined task that doesn't need a larger model.

Transcript note:
  Most fitness videos have auto-generated captions. The intro (~first 2 min)
  is where trainers explain difficulty, equipment, and workout structure.
  If transcripts are unavailable, we fall back to title + description only.
"""

import json
import logging
import time
from datetime import datetime, timezone

import anthropic
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

from .db import get_connection

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"

# How many transcript segments to fetch (each ~6 sec → ~25 segments ≈ first 2.5 min)
TRANSCRIPT_SEGMENTS = 25

# How often to poll the batch API for completion (seconds)
BATCH_POLL_INTERVAL = 30

SYSTEM_PROMPT = """You are a fitness video classifier. Given a YouTube workout video's metadata, classify it accurately.

Return ONLY a valid JSON object with these exact fields:
{
  "workout_type": "HIIT" | "Strength" | "Mobility" | "Cardio" | "Yoga" | "Pilates" | "Dance" | "Other",
  "body_focus": "upper" | "lower" | "full" | "core" | "any",
  "difficulty": "beginner" | "intermediate" | "advanced",
  "has_warmup": true | false,
  "has_cooldown": true | false
}

Guidelines:
- workout_type "HIIT"     = high-intensity interval training, tabata, circuit training
- workout_type "Strength" = weight training, resistance training, dumbbell/barbell workouts
- workout_type "Cardio"   = running, cycling, traditional aerobics (non-dance)
- workout_type "Mobility" = stretching, foam rolling, flexibility work (NOT yoga or pilates)
- workout_type "Yoga"     = yoga flows, vinyasa, hatha, yin yoga, ashtanga, restorative yoga
- workout_type "Pilates"  = mat pilates, reformer pilates, barre workouts
- workout_type "Dance"    = Zumba, Bollywood dance fitness, dance cardio, hip-hop dance workouts
- workout_type "Other"    = vlogs, Q&As, nutrition tips, challenges, non-workout content; also: progress/transformation videos ("how much muscle I gained"), reaction/critique/commentary videos ("scientists critique workouts"), educational explainers about exercise science, challenge tracking ("365 days"), and any video where the viewer is not expected to follow along and exercise
- body_focus "any"        = when focus cannot be determined from available info
- difficulty              = use "intermediate" as default when unclear
- has_warmup/has_cooldown = true only when explicitly mentioned or clearly evident
- Return ONLY the JSON object, no explanation, no markdown code fences"""


# ─── Transcript fetching ──────────────────────────────────────────────────────

def _fetch_transcript_intro(video_id: str) -> str | None:
    """
    Fetch the first ~2 minutes of a video's transcript.

    Returns the text as a single string, or None if unavailable.
    Tries English first, then falls back to any available language.
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Prefer manually created English, then auto-generated English, then any
        try:
            transcript = transcript_list.find_transcript(["en"])
        except NoTranscriptFound:
            transcript = transcript_list.find_generated_transcript(["en"])

        segments = transcript.fetch()
        intro = segments[:TRANSCRIPT_SEGMENTS]
        return " ".join(seg["text"] for seg in intro).strip()

    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
        return None
    except Exception as e:
        logger.debug(f"Transcript fetch failed for {video_id}: {e}")
        return None


# ─── Classification prompt ────────────────────────────────────────────────────

def _build_user_message(video: dict, transcript_intro: str | None) -> str:
    """Assemble the user message sent to Claude."""
    lines = [
        f"Title: {video['title']}",
        f"Duration: {video['duration_sec'] // 60} minutes" if video['duration_sec'] else "",
        f"Tags: {video['tags']}" if video['tags'] else "",
        "",
        f"Description:\n{(video['description'] or '')[:800]}",
    ]

    if transcript_intro:
        lines += ["", f"Transcript intro (first ~2 min):\n{transcript_intro}"]

    return "\n".join(line for line in lines if line is not None)


def _parse_classification(raw: str) -> dict | None:
    """
    Parse Claude's JSON response into a classification dict.
    Returns None if parsing fails.
    """
    try:
        # Strip any accidental markdown fences just in case
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(cleaned)

        valid_types  = {"HIIT", "Strength", "Mobility", "Cardio", "Yoga", "Pilates", "Dance", "Other"}
        valid_focus  = {"upper", "lower", "full", "core", "any"}
        valid_diff   = {"beginner", "intermediate", "advanced"}

        return {
            "workout_type": data["workout_type"] if data.get("workout_type") in valid_types else "Other",
            "body_focus":   data["body_focus"]   if data.get("body_focus")   in valid_focus  else "any",
            "difficulty":   data["difficulty"]   if data.get("difficulty")   in valid_diff   else "intermediate",
            "has_warmup":   1 if data.get("has_warmup")   else 0,
            "has_cooldown": 1 if data.get("has_cooldown") else 0,
        }
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to parse classification response: {e}\nRaw: {raw[:200]}")
        return None


# ─── Database write ───────────────────────────────────────────────────────────

def _save_classification(video_id: str, classification: dict):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO classifications
                (video_id, workout_type, body_focus, difficulty,
                 has_warmup, has_cooldown, classified_at)
            VALUES
                (:video_id, :workout_type, :body_focus, :difficulty,
                 :has_warmup, :has_cooldown, :classified_at)
        """, {
            "video_id":     video_id,
            "workout_type": classification["workout_type"],
            "body_focus":   classification["body_focus"],
            "difficulty":   classification["difficulty"],
            "has_warmup":   classification["has_warmup"],
            "has_cooldown": classification["has_cooldown"],
            "classified_at": datetime.now(timezone.utc).isoformat(),
        })


def _fetch_unclassified_videos() -> list[dict]:
    """Return all videos that don't yet have a classification entry."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT v.*
            FROM   videos v
            LEFT JOIN classifications c ON c.video_id = v.id
            WHERE  c.video_id IS NULL
            ORDER  BY v.published_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ─── Batch classification ─────────────────────────────────────────────────────

def classify_unclassified_batch(api_key: str) -> int:
    """
    Classify all unclassified videos using Anthropic's Batch API.

    Phases:
      1. Fetch transcripts and build one request object per video (sequential)
      2. Submit all requests in a single Batch API call (50% cheaper than standard)
      3. Poll until the batch completes
      4. Parse responses and save classifications to DB

    Skips videos shorter than 3 minutes (likely Shorts / promos).
    Returns count of successfully classified videos.
    """
    client = anthropic.Anthropic(api_key=api_key)
    videos = _fetch_unclassified_videos()

    # Filter out very short videos (Shorts / trailers)
    videos = [v for v in videos if (v["duration_sec"] or 0) >= 180]

    total = len(videos)
    if total == 0:
        logger.info("No unclassified videos found.")
        return 0

    # ── Phase 1: Build batch requests (fetch transcripts sequentially) ─────────
    logger.info(f"Phase 1/3: Fetching transcripts and building {total} requests...")
    requests = []
    for i, video in enumerate(videos, 1):
        if i % 100 == 0 or i == 1:
            logger.info(f"  [{i}/{total}] {video['channel_name']} - {video['title'][:60]}")

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

    # ── Phase 2: Submit batch ──────────────────────────────────────────────────
    logger.info(f"Phase 2/3: Submitting batch of {total} requests to Anthropic...")
    batch = client.messages.batches.create(requests=requests)
    logger.info(f"Batch submitted - ID: {batch.id}")

    # ── Phase 3: Poll until complete ───────────────────────────────────────────
    logger.info(f"Phase 3/3: Waiting for batch to complete (polling every {BATCH_POLL_INTERVAL}s)...")
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        counts = batch.request_counts
        done = counts.succeeded + counts.errored + counts.canceled + counts.expired
        logger.info(f"  Status: {batch.processing_status} - {done}/{total} done")
        if batch.processing_status == "ended":
            break
        time.sleep(BATCH_POLL_INTERVAL)

    # ── Phase 4: Process results ───────────────────────────────────────────────
    classified = 0
    failed = 0
    for result in client.messages.batches.results(batch.id):
        if result.result.type == "succeeded":
            raw = result.result.message.content[0].text
            classification = _parse_classification(raw)
            if classification:
                _save_classification(result.custom_id, classification)
                classified += 1
            else:
                failed += 1
        else:
            logger.warning(f"Request failed for video {result.custom_id}: {result.result.type}")
            failed += 1

    logger.info(f"Classification complete: {classified}/{total} classified, {failed} failed")
    return classified
