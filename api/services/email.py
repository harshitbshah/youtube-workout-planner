"""
email.py — Resend-powered transactional emails.
"""
import logging
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import resend
from jinja2 import Environment, FileSystemLoader

from src.planner import get_upcoming_monday

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_jinja = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)


def _format_duration(duration_sec: int | None) -> str:
    if not duration_sec:
        return ""
    mins = round(duration_sec / 60)
    return f"{mins} min"


def _extract_youtube_id(url: str) -> str | None:
    """Extract the YouTube video ID from a watch or short URL."""
    parsed = urlparse(url)
    if parsed.hostname in ("www.youtube.com", "youtube.com"):
        return parse_qs(parsed.query).get("v", [None])[0]
    if parsed.hostname == "youtu.be":
        return parsed.path.lstrip("/")
    return None


def _workout_type_style(workout_type: str | None) -> dict:
    """Return bg/text colour pair for the workout type pill."""
    styles = {
        "strength": {"bg": "#fef3c7", "color": "#92400e"},
        "hiit":     {"bg": "#fee2e2", "color": "#991b1b"},
        "cardio":   {"bg": "#d1fae5", "color": "#065f46"},
        "mobility": {"bg": "#ede9fe", "color": "#4c1d95"},
    }
    return styles.get((workout_type or "").lower(), {"bg": "#f3f4f6", "color": "#374151"})


def send_weekly_plan_email(user, plan: list[dict]) -> None:
    """
    Send the weekly plan email to the user.

    user  — SQLAlchemy User instance (needs .email, .display_name)
    plan  — list of {"day": str, "video": dict | None} from generate_weekly_plan_for_user
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY not set")

    resend.api_key = api_key

    app_url = os.environ.get("APP_URL", "https://planmyworkout.app")
    from_email = os.environ.get("FROM_EMAIL", "hello@planmyworkout.app")

    # Enrich plan days with display helpers
    enriched_days = []
    active_days = 0
    total_duration_sec = 0

    for entry in plan:
        video = entry.get("video")
        if video:
            active_days += 1
            total_duration_sec += video.get("duration_sec") or 0
            vid_id = _extract_youtube_id(video.get("url", ""))
            thumbnail_url = (
                f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg" if vid_id else None
            )
            enriched_days.append({
                "day": entry["day"].capitalize(),
                "is_rest": False,
                "video": video,
                "duration_str": _format_duration(video.get("duration_sec")),
                "type_style": _workout_type_style(video.get("workout_type")),
                "thumbnail_url": thumbnail_url,
            })
        else:
            enriched_days.append({
                "day": entry["day"].capitalize(),
                "is_rest": True,
            })

    total_duration_min = round(total_duration_sec / 60)

    week_start = get_upcoming_monday()
    week_start_str = week_start.strftime("%-d %B")  # e.g. "10 March"

    template = _jinja.get_template("weekly_plan_email.html")
    html = template.render(
        display_name=user.display_name or user.email.split("@")[0],
        week_start=week_start_str,
        active_days=active_days,
        total_duration_min=total_duration_min,
        days=enriched_days,
        dashboard_url=f"{app_url}/dashboard",
        unsubscribe_url=f"{app_url}/settings#notifications",
    )

    resend.Emails.send({
        "from": f"Plan My Workout <{from_email}>",
        "to": user.email,
        "subject": f"Your workout plan for the week of {week_start_str}",
        "html": html,
    })

    logger.info(f"[email] Weekly plan sent to {user.email} for week of {week_start_str}")


CATEGORY_LABELS = {
    "feedback": "💬 General feedback",
    "help":     "🙋 I need help",
    "bug":      "🐛 Found a bug",
}


def send_feedback_email(user, category: str, message: str) -> None:
    """
    Forward a user feedback submission to the admin inbox.

    user     — SQLAlchemy User instance (needs .email, .display_name)
    category — one of: feedback | help | bug
    message  — free-text from the user
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY not set")

    resend.api_key = api_key

    from_email = os.environ.get("FROM_EMAIL", "hello@planmyworkout.app")
    admin_email = os.environ.get("ADMIN_EMAIL", "harshitspeaks@gmail.com")
    label = CATEGORY_LABELS.get(category, category)
    display = user.display_name or user.email.split("@")[0]

    resend.Emails.send({
        "from": f"Plan My Workout <{from_email}>",
        "to": admin_email,
        "reply_to": user.email,
        "subject": f"[{label}] from {display}",
        "html": (
            f"<p><strong>From:</strong> {display} ({user.email})</p>"
            f"<p><strong>Category:</strong> {label}</p>"
            f"<hr/>"
            f"<p>{message.replace(chr(10), '<br/>')}</p>"
        ),
    })

    logger.info(f"[email] Feedback ({category}) received from {user.email}")
