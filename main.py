"""
main.py — Entry point for the YouTube Workout Planner.

Usage:
  python main.py --init       First-time full scan + classify all channels
  python main.py --run        Weekly: sync new videos + generate plan + refresh playlist
  python main.py --dry-run    Generate and print the plan without touching the playlist

Required environment variables (set as GitHub Secrets for automated runs):
  YOUTUBE_API_KEY               YouTube Data API v3 key (read-only)
  ANTHROPIC_API_KEY             Claude API key (for video classification)
  YOUTUBE_CLIENT_ID             OAuth client ID  (needed for --run, not --init)
  YOUTUBE_CLIENT_SECRET         OAuth client secret
  YOUTUBE_OAUTH_REFRESH_TOKEN   OAuth refresh token (from scripts/get_oauth_token.py)
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from src.db import init_db
from src.scanner import build_youtube_client, scan_all_channels
from src.classifier import classify_unclassified_batch
from src.planner import generate_weekly_plan, format_plan_summary, get_upcoming_monday
from src.playlist import build_oauth_client, refresh_playlist

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        logger.error("config.yaml not found. Have you set up the project?")
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def require_env(name: str) -> str:
    """Return the value of an env var, or exit with a clear error message."""
    value = os.environ.get(name, "").strip()
    if not value:
        logger.error(
            f"Required environment variable '{name}' is not set.\n"
            f"  • For local runs:  export {name}=your_value\n"
            f"  • For GitHub Actions: add it to Settings → Secrets → Actions"
        )
        sys.exit(1)
    return value


def validate_config(config: dict):
    """Check config.yaml has the minimum required fields."""
    if not config.get("channels"):
        logger.error("No channels defined in config.yaml.")
        sys.exit(1)
    for ch in config["channels"]:
        if not ch.get("url"):
            logger.error(f"Channel '{ch.get('name', '?')}' is missing a URL in config.yaml.")
            sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_init(config: dict):
    """
    First-time initialisation:
      1. Create DB tables
      2. Full scan of every channel (fetches entire back-catalogue)
      3. Classify all videos with Claude

    Run this once after cloning the repo and filling in config.yaml.
    Takes 15–40 minutes depending on channel sizes. Safe to re-run
    (duplicate videos and classifications are silently skipped).
    """
    logger.info("=" * 60)
    logger.info("INIT — First-time setup")
    logger.info("=" * 60)

    init_db()

    api_key       = require_env("YOUTUBE_API_KEY")
    anthropic_key = require_env("ANTHROPIC_API_KEY")

    youtube = build_youtube_client(api_key)

    logger.info(f"Scanning {len(config['channels'])} channel(s)...")
    total_videos = scan_all_channels(youtube, config["channels"])
    logger.info(f"Scan complete: {total_videos} videos saved to library.")

    logger.info("Classifying all videos (this takes a while on first run)...")
    classified = classify_unclassified_batch(anthropic_key)
    logger.info(f"Classification complete: {classified} videos classified.")

    logger.info("=" * 60)
    logger.info("INIT complete.")
    logger.info("Next step: run  python main.py --dry-run  to preview your first plan.")
    logger.info("=" * 60)


def cmd_run(config: dict, dry_run: bool = False):
    """
    Weekly run (or dry-run):
      1. Incremental scan — fetch videos published in the last 8 days
      2. Classify any newly scanned videos
      3. Generate the weekly workout plan
      4. Refresh the YouTube playlist  (skipped on --dry-run)

    The 8-day window (not 7) gives a buffer for timezone differences
    and ensures no new videos slip through on the boundary.
    """
    mode = "DRY RUN" if dry_run else "WEEKLY RUN"
    logger.info("=" * 60)
    logger.info(f"{mode}")
    logger.info("=" * 60)

    init_db()

    api_key       = require_env("YOUTUBE_API_KEY")
    anthropic_key = require_env("ANTHROPIC_API_KEY")

    youtube    = build_youtube_client(api_key)
    since_date = datetime.now(timezone.utc) - timedelta(days=8)

    # ── 1. Sync new videos ────────────────────────────────────────────────────
    logger.info(f"Checking for new videos since {since_date.date()}...")
    new_videos = scan_all_channels(youtube, config["channels"], since_date=since_date)
    logger.info(f"New videos synced: {new_videos}")

    # ── 2. Classify any unclassified videos (new or previously missed) ────────
    classified = classify_unclassified_batch(anthropic_key)
    if classified:
        logger.info(f"Newly classified: {classified} videos")

    # ── 3. Generate the plan ──────────────────────────────────────────────────
    logger.info("Generating weekly plan...")
    plan       = generate_weekly_plan(config)
    week_start = get_upcoming_monday().isoformat()
    summary    = format_plan_summary(plan, week_start)

    # Always print the plan — visible in GitHub Actions logs
    print("\n" + summary + "\n")

    if dry_run:
        logger.info("Dry run complete. Playlist not updated.")
        return

    # ── 4. Refresh YouTube playlist ───────────────────────────────────────────
    playlist_id = config.get("playlist", {}).get("id", "").strip()
    if not playlist_id:
        logger.warning(
            "No playlist ID set in config.yaml (playlist.id). "
            "Skipping playlist update — plan was printed above."
        )
        return

    client_id     = require_env("YOUTUBE_CLIENT_ID")
    client_secret = require_env("YOUTUBE_CLIENT_SECRET")
    refresh_token = require_env("YOUTUBE_OAUTH_REFRESH_TOKEN")

    logger.info("Connecting to YouTube (OAuth)...")
    youtube_oauth = build_oauth_client(client_id, client_secret, refresh_token)

    refresh_playlist(youtube_oauth, playlist_id, plan, summary)

    logger.info("=" * 60)
    logger.info("Weekly run complete.")
    logger.info(f"Playlist: https://youtube.com/playlist?list={playlist_id}")
    logger.info("=" * 60)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="YouTube Workout Planner — curate a weekly workout plan from your favourite channels.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python main.py --init        # run once after setup
  python main.py --dry-run     # preview next week's plan
  python main.py --run         # full weekly run (called by GitHub Actions)
        """,
    )
    parser.add_argument("--init",    action="store_true", help="First-time full scan and classification")
    parser.add_argument("--run",     action="store_true", help="Weekly sync, plan generation, and playlist refresh")
    parser.add_argument("--dry-run", action="store_true", help="Generate and print plan without updating playlist")
    args = parser.parse_args()

    if not any([args.init, args.run, args.dry_run]):
        parser.print_help()
        sys.exit(0)

    config = load_config()
    validate_config(config)

    if args.init:
        cmd_init(config)
    elif args.run:
        cmd_run(config, dry_run=False)
    elif args.dry_run:
        cmd_run(config, dry_run=True)


if __name__ == "__main__":
    main()
