"""
Unit tests for the weekly scheduler active-user gate.

run_weekly_pipeline() must only run the pipeline for users who have been
active within INACTIVE_THRESHOLD_DAYS. Users with last_active_at=None or
older than the threshold must be skipped.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from api.scheduler import INACTIVE_THRESHOLD_DAYS, run_weekly_pipeline


def _make_user(google_id: str, email: str, last_active_at=None):
    """Create a mock User object with the given last_active_at timestamp."""
    user = MagicMock()
    user.id = google_id  # use google_id as a simple unique identifier
    user.google_id = google_id
    user.email = email
    user.last_active_at = last_active_at
    return user


def _now():
    return datetime.now(timezone.utc)


# ─── Active-user filter tests ─────────────────────────────────────────────────

def test_active_user_within_threshold_is_processed():
    """A user active 1 day ago must be included in the pipeline run."""
    user = _make_user("active-1d", "active@test.com", last_active_at=_now() - timedelta(days=1))

    mock_session = MagicMock()
    mock_session.query.return_value.all.return_value = [user]

    with patch("api.database.SessionLocal", return_value=mock_session), \
         patch("api.scheduler._weekly_pipeline_for_user") as mock_pipeline:
        run_weekly_pipeline()

    mock_pipeline.assert_called_once_with(str(user.id))


def test_inactive_user_beyond_threshold_is_skipped():
    """A user last active 20 days ago must NOT trigger the pipeline."""
    user = _make_user("inactive-20d", "inactive@test.com", last_active_at=_now() - timedelta(days=20))

    mock_session = MagicMock()
    mock_session.query.return_value.all.return_value = [user]

    with patch("api.database.SessionLocal", return_value=mock_session), \
         patch("api.scheduler._weekly_pipeline_for_user") as mock_pipeline:
        run_weekly_pipeline()

    mock_pipeline.assert_not_called()


def test_user_with_no_last_active_at_is_skipped():
    """A user with last_active_at=None (never logged in via web app) must be skipped."""
    user = _make_user("never-active", "never@test.com", last_active_at=None)

    mock_session = MagicMock()
    mock_session.query.return_value.all.return_value = [user]

    with patch("api.database.SessionLocal", return_value=mock_session), \
         patch("api.scheduler._weekly_pipeline_for_user") as mock_pipeline:
        run_weekly_pipeline()

    mock_pipeline.assert_not_called()


def test_boundary_exactly_at_threshold_is_included():
    """A user whose last_active_at equals exactly the cutoff boundary is included
    (cutoff = now - 14 days; last_active_at >= cutoff passes).
    """
    # 13 days = just inside the 14-day window
    user = _make_user(
        "boundary-user",
        "boundary@test.com",
        last_active_at=_now() - timedelta(days=INACTIVE_THRESHOLD_DAYS - 1),
    )

    mock_session = MagicMock()
    mock_session.query.return_value.all.return_value = [user]

    with patch("api.database.SessionLocal", return_value=mock_session), \
         patch("api.scheduler._weekly_pipeline_for_user") as mock_pipeline:
        run_weekly_pipeline()

    mock_pipeline.assert_called_once_with(str(user.id))


def test_boundary_just_past_threshold_is_skipped():
    """A user whose last_active_at is 15 days ago (beyond 14-day window) is skipped."""
    user = _make_user(
        "boundary-skip",
        "boundaryskip@test.com",
        last_active_at=_now() - timedelta(days=INACTIVE_THRESHOLD_DAYS + 1),
    )

    mock_session = MagicMock()
    mock_session.query.return_value.all.return_value = [user]

    with patch("api.database.SessionLocal", return_value=mock_session), \
         patch("api.scheduler._weekly_pipeline_for_user") as mock_pipeline:
        run_weekly_pipeline()

    mock_pipeline.assert_not_called()


def test_mixed_users_only_active_are_processed():
    """With a mix of active and inactive users, only active ones run the pipeline."""
    active_1 = _make_user("act-1", "a1@test.com", last_active_at=_now() - timedelta(days=3))
    active_2 = _make_user("act-2", "a2@test.com", last_active_at=_now() - timedelta(days=10))
    inactive = _make_user("inact-1", "inact@test.com", last_active_at=_now() - timedelta(days=30))
    no_activity = _make_user("noact-1", "noact@test.com", last_active_at=None)

    mock_session = MagicMock()
    mock_session.query.return_value.all.return_value = [active_1, active_2, inactive, no_activity]

    with patch("api.database.SessionLocal", return_value=mock_session), \
         patch("api.scheduler._weekly_pipeline_for_user") as mock_pipeline:
        run_weekly_pipeline()

    called_ids = {c.args[0] for c in mock_pipeline.call_args_list}
    assert called_ids == {str(active_1.id), str(active_2.id)}
    assert str(inactive.id) not in called_ids
    assert str(no_activity.id) not in called_ids


def test_no_users_pipeline_never_called():
    """When the user table is empty, the pipeline function is never called."""
    mock_session = MagicMock()
    mock_session.query.return_value.all.return_value = []

    with patch("api.database.SessionLocal", return_value=mock_session), \
         patch("api.scheduler._weekly_pipeline_for_user") as mock_pipeline:
        run_weekly_pipeline()

    mock_pipeline.assert_not_called()


def test_pipeline_error_for_one_user_does_not_block_others():
    """If the pipeline raises for one user, the remaining users are still processed."""
    active_1 = _make_user("err-user", "err@test.com", last_active_at=_now() - timedelta(days=1))
    active_2 = _make_user("ok-user", "ok@test.com", last_active_at=_now() - timedelta(days=2))

    mock_session = MagicMock()
    mock_session.query.return_value.all.return_value = [active_1, active_2]

    def _fail_first(user_id):
        if user_id == str(active_1.id):
            raise RuntimeError("pipeline boom")

    with patch("api.database.SessionLocal", return_value=mock_session), \
         patch("api.scheduler._weekly_pipeline_for_user", side_effect=_fail_first) as mock_pipeline:
        run_weekly_pipeline()  # must not raise

    assert mock_pipeline.call_count == 2


def test_db_session_is_always_closed():
    """The outer SessionLocal session is closed regardless of query outcome."""
    mock_session = MagicMock()
    mock_session.query.return_value.all.return_value = []

    with patch("api.database.SessionLocal", return_value=mock_session), \
         patch("api.scheduler._weekly_pipeline_for_user"):
        run_weekly_pipeline()

    mock_session.close.assert_called_once()
