"""
scheduler.py - APScheduler weekly cron for all users.

Runs every Sunday at 18:00 UTC:
  For each user who has been active in the last 14 days AND has at least one channel:
    1. Incremental scan all their channels
    2. Classify new videos
    3. Generate next week's plan
    4. Send weekly plan email (if email_notifications=True)
    5. Auto-publish to YouTube playlist (if credentials valid)

Design intent
─────────────
The web app is the primary interface. Users log in, view their plan, optionally swap
videos, and click "Publish to YouTube" - all within the app. The YouTube playlist is
a convenience output so users can play videos directly from the YouTube app without
signing in to the web app each time.

Any authenticated request (viewing the dashboard, swapping a video, clicking Publish)
updates `user.last_active_at`. We use that as the activity gate for the cron. Users
who haven't opened the app in 14+ days have no plan to act on - skip them to save
YouTube API quota and Anthropic credits.

The 14-day threshold tolerates a user missing one week (8–13 days absent) and still
getting a plan on the next Sunday. Only users absent for two full weeks are skipped.

Started/stopped via FastAPI lifespan in main.py.
"""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


def _weekly_pipeline_for_user(user_id: str):
    """Run the full weekly pipeline for one user. Creates its own DB session."""
    from .database import SessionLocal
    from .models import Channel, User, UserChannel
    from .services.classifier import classify_for_user, rule_classify_for_user
    from .services.planner import can_fill_plan, generate_weekly_plan_for_user
    from .services.scanner import scan_channel

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            logger.info(f"[weekly] user={user_id} not found, skipping")
            return

        channels = (
            session.query(Channel)
            .join(UserChannel, UserChannel.channel_id == Channel.id)
            .filter(UserChannel.user_id == user_id)
            .all()
        )
        if not channels:
            logger.info(f"[weekly] user={user_id} has no channels, skipping")
            return

        # Step 1: incremental scan all channels (skip inactive to save YouTube API quota)
        total_new = 0
        for channel in channels:
            try:
                new = scan_channel(session, channel, skip_if_inactive=True)
                total_new += new
            except Exception as e:
                logger.error(f"[weekly] Scan failed for channel {channel.name}: {e}")

        logger.info(f"[weekly] user={user_id}: {total_new} new videos across {len(channels)} channels")

        # Step 2: rule-classify new videos (free)
        rule_classify_for_user(session, user_id)

        # Step 3: submit Anthropic batch only if plan can't be filled from current pool
        if not can_fill_plan(session, user_id):
            try:
                classified = classify_for_user(session, user_id)
                logger.info(f"[weekly] user={user_id}: {classified} videos classified")
            except Exception as e:
                logger.error(f"[weekly] Classification failed for user {user_id}: {e}")
        else:
            logger.info(f"[weekly] user={user_id}: plan fillable from existing pool - skipping Anthropic batch")

        # Step 3: generate next week's plan
        plan = None
        try:
            plan = generate_weekly_plan_for_user(session, user_id)
            logger.info(f"[weekly] user={user_id}: plan generated")
        except Exception as e:
            logger.error(f"[weekly] Plan generation failed for user {user_id}: {e}")
            return  # can't publish or email without a plan

        # Step 4: send weekly plan email
        if user.email_notifications:
            from .services.email import send_weekly_plan_email
            try:
                send_weekly_plan_email(user, plan)
                logger.info(f"[weekly] user={user_id}: plan email sent to {user.email}")
            except Exception as e:
                logger.error(f"[weekly] user={user_id}: email failed - {e}")
                # Never let email failure break the pipeline

        # Step 5: auto-publish if user has valid YouTube credentials
        from .models import UserCredentials
        from .services.publisher import (
            YouTubeAccessRevokedError,
            YouTubeNotConnectedError,
            publish_plan_for_user,
        )
        from src.planner import get_upcoming_monday

        creds = session.query(UserCredentials).filter(UserCredentials.user_id == user_id).first()
        if creds and creds.youtube_refresh_token and creds.credentials_valid:
            week_start = get_upcoming_monday()
            try:
                result = publish_plan_for_user(session, user_id, week_start)
                logger.info(
                    f"[weekly] user={user_id}: auto-published {result['video_count']} videos"
                )
            except (YouTubeNotConnectedError, YouTubeAccessRevokedError) as e:
                logger.warning(f"[weekly] user={user_id}: YouTube publish skipped - {e}")
            except Exception as e:
                logger.error(f"[weekly] user={user_id}: publish failed - {e}")

    finally:
        session.close()


INACTIVE_THRESHOLD_DAYS = 14  # skip users who haven't opened the app in this many days


def run_weekly_pipeline():
    """Fetch active users and run the pipeline for each.

    Only processes users who have been active within INACTIVE_THRESHOLD_DAYS.
    Users who haven't logged in (or published) recently have no plan to act on
    and are skipped to conserve YouTube API quota and Anthropic credits.
    """
    from .database import SessionLocal
    from .models import User

    logger.info("[weekly] Starting weekly pipeline for all users")
    cutoff = datetime.now(timezone.utc) - timedelta(days=INACTIVE_THRESHOLD_DAYS)

    session = SessionLocal()
    try:
        all_users = session.query(User).all()
        active_users = [u for u in all_users if u.last_active_at and u.last_active_at >= cutoff]
        skipped = len(all_users) - len(active_users)
        logger.info(
            f"[weekly] {len(active_users)} active users to process, "
            f"{skipped} inactive (>{INACTIVE_THRESHOLD_DAYS}d) skipped"
        )
        user_ids = [str(u.id) for u in active_users]
    finally:
        session.close()

    for user_id in user_ids:
        try:
            _weekly_pipeline_for_user(user_id)
        except Exception as e:
            logger.error(f"[weekly] Pipeline failed for user {user_id}: {e}")

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
    logger.info("[scheduler] Started - weekly pipeline scheduled for Sunday 18:00 UTC")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[scheduler] Stopped")
