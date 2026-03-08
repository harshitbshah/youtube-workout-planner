"""
scheduler.py — APScheduler weekly cron for all users.

Runs every Sunday at 18:00 UTC:
  For each user with at least one channel:
    1. Incremental scan all their channels
    2. Classify new videos
    3. Generate next week's plan

Started/stopped via FastAPI lifespan in main.py.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


def _weekly_pipeline_for_user(user_id: str):
    """Run the full weekly pipeline for one user. Creates its own DB session."""
    from .database import SessionLocal
    from .models import Channel
    from .services.classifier import classify_for_user
    from .services.scanner import scan_channel
    from .services.planner import generate_weekly_plan_for_user

    session = SessionLocal()
    try:
        channels = session.query(Channel).filter(Channel.user_id == user_id).all()
        if not channels:
            logger.info(f"[weekly] user={user_id} has no channels, skipping")
            return

        # Step 1: incremental scan all channels
        total_new = 0
        for channel in channels:
            try:
                new = scan_channel(session, channel)
                total_new += new
            except Exception as e:
                logger.error(f"[weekly] Scan failed for channel {channel.name}: {e}")

        logger.info(f"[weekly] user={user_id}: {total_new} new videos across {len(channels)} channels")

        # Step 2: classify new videos
        if total_new > 0:
            try:
                classified = classify_for_user(session, user_id)
                logger.info(f"[weekly] user={user_id}: {classified} videos classified")
            except Exception as e:
                logger.error(f"[weekly] Classification failed for user {user_id}: {e}")

        # Step 3: generate next week's plan
        try:
            generate_weekly_plan_for_user(session, user_id)
            logger.info(f"[weekly] user={user_id}: plan generated")
        except Exception as e:
            logger.error(f"[weekly] Plan generation failed for user {user_id}: {e}")

    finally:
        session.close()


def run_weekly_pipeline():
    """Fetch all users and run the pipeline for each."""
    from .database import SessionLocal
    from .models import User

    logger.info("[weekly] Starting weekly pipeline for all users")
    session = SessionLocal()
    try:
        users = session.query(User).all()
        logger.info(f"[weekly] {len(users)} users to process")
    finally:
        session.close()

    for user in users:
        try:
            _weekly_pipeline_for_user(str(user.id))
        except Exception as e:
            logger.error(f"[weekly] Pipeline failed for user {user.id}: {e}")

    logger.info("[weekly] Weekly pipeline complete")


def start_scheduler():
    """Register the weekly job and start the scheduler."""
    scheduler.add_job(
        run_weekly_pipeline,
        trigger="cron",
        day_of_week="sun",
        hour=18,
        minute=0,
        id="weekly_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[scheduler] Started — weekly pipeline scheduled for Sunday 18:00 UTC")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[scheduler] Stopped")
