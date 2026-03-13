"""
tests/api/test_email.py — Unit tests for api/services/email.py

Mocks resend.Emails.send and src.planner.get_upcoming_monday so tests
run with no network access and a deterministic week_start date.
"""

import os
from datetime import date
from unittest.mock import patch

import pytest

from tests.api.helpers import make_mock_user as _make_user


def _make_plan(active_days=3):
    """Return a minimal plan list with active_days workout days + rest days to fill 7."""
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    plan = []
    for i, day in enumerate(days):
        if i < active_days:
            plan.append({
                "day": day,
                "video": {
                    "title": f"Workout Video {i + 1}",
                    "url": f"https://youtube.com/watch?v=abc{i}",
                    "channel_name": "Fitness Channel",
                    "duration_sec": 1800,
                    "workout_type": "Strength",
                },
            })
        else:
            plan.append({"day": day, "video": None})
    return plan


FIXED_MONDAY = date(2026, 3, 16)  # a Monday


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_send_calls_resend_with_correct_subject():
    """send_weekly_plan_email calls resend.Emails.send with the right subject."""
    with (
        patch.dict(os.environ, {"RESEND_API_KEY": "re_test123"}),
        patch("api.services.email.get_upcoming_monday", return_value=FIXED_MONDAY),
        patch("api.services.email.resend") as mock_resend,
    ):
        from api.services.email import send_weekly_plan_email
        send_weekly_plan_email(_make_user(), _make_plan())

    mock_resend.Emails.send.assert_called_once()
    call_kwargs = mock_resend.Emails.send.call_args[0][0]
    assert "week of 16 March" in call_kwargs["subject"]


def test_send_html_contains_video_titles():
    """HTML body includes each active day's video title."""
    plan = _make_plan(active_days=2)
    with (
        patch.dict(os.environ, {"RESEND_API_KEY": "re_test123"}),
        patch("api.services.email.get_upcoming_monday", return_value=FIXED_MONDAY),
        patch("api.services.email.resend") as mock_resend,
    ):
        from api.services.email import send_weekly_plan_email
        send_weekly_plan_email(_make_user(), plan)

    html = mock_resend.Emails.send.call_args[0][0]["html"]
    assert "Workout Video 1" in html
    assert "Workout Video 2" in html


def test_send_html_contains_youtube_urls():
    """HTML body includes YouTube URLs for active days."""
    plan = _make_plan(active_days=1)
    with (
        patch.dict(os.environ, {"RESEND_API_KEY": "re_test123"}),
        patch("api.services.email.get_upcoming_monday", return_value=FIXED_MONDAY),
        patch("api.services.email.resend") as mock_resend,
    ):
        from api.services.email import send_weekly_plan_email
        send_weekly_plan_email(_make_user(), plan)

    html = mock_resend.Emails.send.call_args[0][0]["html"]
    assert "https://youtube.com/watch?v=abc0" in html


def test_send_html_excludes_rest_days():
    """HTML body does not include rest days — only active workout days are shown."""
    plan = _make_plan(active_days=3)
    with (
        patch.dict(os.environ, {"RESEND_API_KEY": "re_test123"}),
        patch("api.services.email.get_upcoming_monday", return_value=FIXED_MONDAY),
        patch("api.services.email.resend") as mock_resend,
    ):
        from api.services.email import send_weekly_plan_email
        send_weekly_plan_email(_make_user(), plan)

    html = mock_resend.Emails.send.call_args[0][0]["html"]
    assert "Recovery" not in html
    assert "Workout Video 1" in html
    assert "Workout Video 2" in html
    assert "Workout Video 3" in html


def test_send_to_correct_recipient():
    """Email is addressed to the user's email address."""
    user = _make_user(email="harshit@example.com")
    with (
        patch.dict(os.environ, {"RESEND_API_KEY": "re_test123"}),
        patch("api.services.email.get_upcoming_monday", return_value=FIXED_MONDAY),
        patch("api.services.email.resend") as mock_resend,
    ):
        from api.services.email import send_weekly_plan_email
        send_weekly_plan_email(user, _make_plan())

    call_kwargs = mock_resend.Emails.send.call_args[0][0]
    assert call_kwargs["to"] == "harshit@example.com"


def test_raises_when_api_key_missing():
    """Raises RuntimeError if RESEND_API_KEY is not set."""
    env = {k: v for k, v in os.environ.items() if k != "RESEND_API_KEY"}
    with patch.dict(os.environ, env, clear=True):
        from api.services.email import send_weekly_plan_email
        with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
            send_weekly_plan_email(_make_user(), _make_plan())


def test_display_name_fallback_to_email_prefix():
    """When display_name is None, the email prefix is used as the name."""
    user = _make_user(email="jane@example.com", display_name=None)
    with (
        patch.dict(os.environ, {"RESEND_API_KEY": "re_test123"}),
        patch("api.services.email.get_upcoming_monday", return_value=FIXED_MONDAY),
        patch("api.services.email.resend") as mock_resend,
    ):
        from api.services.email import send_weekly_plan_email
        send_weekly_plan_email(user, _make_plan())

    html = mock_resend.Emails.send.call_args[0][0]["html"]
    assert "jane" in html


def test_from_email_uses_env_var():
    """FROM_EMAIL env var is used as the sender address."""
    with (
        patch.dict(os.environ, {
            "RESEND_API_KEY": "re_test123",
            "FROM_EMAIL": "custom@myapp.com",
        }),
        patch("api.services.email.get_upcoming_monday", return_value=FIXED_MONDAY),
        patch("api.services.email.resend") as mock_resend,
    ):
        from api.services.email import send_weekly_plan_email
        send_weekly_plan_email(_make_user(), _make_plan())

    call_kwargs = mock_resend.Emails.send.call_args[0][0]
    assert "custom@myapp.com" in call_kwargs["from"]


def test_all_rest_days_plan():
    """An all-rest plan (0 active days) sends successfully without crashing."""
    plan = [{"day": d, "video": None} for d in
            ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]]
    with (
        patch.dict(os.environ, {"RESEND_API_KEY": "re_test123"}),
        patch("api.services.email.get_upcoming_monday", return_value=FIXED_MONDAY),
        patch("api.services.email.resend") as mock_resend,
    ):
        from api.services.email import send_weekly_plan_email
        send_weekly_plan_email(_make_user(), plan)

    mock_resend.Emails.send.assert_called_once()
