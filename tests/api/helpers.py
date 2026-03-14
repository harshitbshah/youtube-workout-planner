"""
Shared test helpers for api unit tests.
"""
from unittest.mock import MagicMock


def make_mock_user(
    email: str = "test@example.com",
    display_name: str | None = "Test User",
    email_notifications: bool = True,
    profile: str | None = None,
    goal: str | None = None,
) -> MagicMock:
    """Return a MagicMock that quacks like a User ORM model."""
    user = MagicMock()
    user.email = email
    user.display_name = display_name
    user.email_notifications = email_notifications
    user.profile = profile
    user.goal = goal
    return user
