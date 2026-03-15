"""
scripts/cleanup_false_positives.py

One-off cleanup: remove false-positive videos from the DB that were scanned
before the pre-classification filters were added to scanner.py.

Filters applied (mirrors api/services/scanner.py):
  1. Title keyword blocklist
  2. Duration > 2 hours (7200 sec)
  3. Duration < 3 minutes (180 sec) - already excluded from classification
     but still clutters the videos table

Run with:
    railway run --service youtube-workout-planner python scripts/cleanup_false_positives.py

Add --dry-run to preview without deleting:
    railway run --service youtube-workout-planner python scripts/cleanup_false_positives.py --dry-run
"""

import os
import sys

from sqlalchemy import create_engine, text

# ─── Filters (keep in sync with api/services/scanner.py) ──────────────────────

_TITLE_BLOCKLIST = {
    # nutrition / food content
    "meal", "recipe", "nutrition", "grocery", "what i eat", "diet", "food",
    # lifestyle / non-workout
    "vlog", "day in my life", "life update", "story time", "haul",
    # talk / informational
    "q&a", "interview", "podcast", "questions and answers",
    # product / promotional
    "review", "unboxing", "giveaway",
    # results / meta
    "transformation", "before and after", "tour", "home gym",
    "behind the scenes",
}

_MAX_DURATION_SEC = 2 * 60 * 60   # 2 hours
_MIN_DURATION_SEC = 3 * 60        # 3 minutes


def is_blocked_title(title: str) -> bool:
    lower = title.lower()
    return any(kw in lower for kw in _TITLE_BLOCKLIST)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        sys.exit("ERROR: DATABASE_URL not set")
    # Normalize Railway's postgres:// prefix
    db_url = db_url.replace("postgres://", "postgresql://", 1)

    engine = create_engine(db_url)

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, title, duration_sec FROM videos")).fetchall()

    total = len(rows)
    to_delete_blocklist = []
    to_delete_too_long = []
    to_delete_too_short = []

    for video_id, title, duration_sec in rows:
        if is_blocked_title(title):
            to_delete_blocklist.append((video_id, title, duration_sec))
        elif duration_sec is not None and duration_sec > _MAX_DURATION_SEC:
            to_delete_too_long.append((video_id, title, duration_sec))
        elif duration_sec is not None and duration_sec < _MIN_DURATION_SEC:
            to_delete_too_short.append((video_id, title, duration_sec))

    all_to_delete = to_delete_blocklist + to_delete_too_long + to_delete_too_short

    print(f"\nTotal videos in DB:      {total}")
    print(f"Blocked title:           {len(to_delete_blocklist)}")
    print(f"Too long (>2h):          {len(to_delete_too_long)}")
    print(f"Too short (<3min):       {len(to_delete_too_short)}")
    print(f"Total to remove:         {len(all_to_delete)}")
    print(f"Remaining after cleanup: {total - len(all_to_delete)}")

    if to_delete_blocklist:
        print("\n── Title blocklist hits ──")
        for vid_id, title, dur in to_delete_blocklist[:20]:
            print(f"  [{dur}s] {title}")
        if len(to_delete_blocklist) > 20:
            print(f"  … and {len(to_delete_blocklist) - 20} more")

    if to_delete_too_long:
        print("\n── Too long (>2h) ──")
        for vid_id, title, dur in to_delete_too_long:
            print(f"  [{dur//60}min] {title}")

    if to_delete_too_short:
        print("\n── Too short (<3min) ──")
        for vid_id, title, dur in to_delete_too_short[:10]:
            print(f"  [{dur}s] {title}")
        if len(to_delete_too_short) > 10:
            print(f"  … and {len(to_delete_too_short) - 10} more")

    if not all_to_delete:
        print("\nNothing to delete.")
        return

    if dry_run:
        print("\n[DRY RUN] No changes made. Remove --dry-run to apply.")
        return

    ids_to_delete = [r[0] for r in all_to_delete]

    with engine.begin() as conn:
        # Classifications reference videos via FK - delete them first
        conn.execute(
            text("DELETE FROM classifications WHERE video_id = ANY(:ids)"),
            {"ids": ids_to_delete},
        )
        # program_history also references videos
        conn.execute(
            text("DELETE FROM program_history WHERE video_id = ANY(:ids)"),
            {"ids": ids_to_delete},
        )
        result = conn.execute(
            text("DELETE FROM videos WHERE id = ANY(:ids)"),
            {"ids": ids_to_delete},
        )
        deleted = result.rowcount

    print(f"\n✓ Deleted {deleted} videos (+ their classifications and plan history entries).")


if __name__ == "__main__":
    main()
