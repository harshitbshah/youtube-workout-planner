"""
Integration test fixtures — run against a real PostgreSQL database.

What makes these different from unit tests:
  - Real PostgreSQL (not SQLite in-memory)
  - Real Alembic migrations applied before the suite runs
  - FK constraints, CASCADE deletes, and DATE types behave exactly as in production
  - Encryption round-trips go through the full DB driver

Setup (one-time):
  The fixture creates workout_planner_test automatically if it doesn't exist.

Run:
  pytest tests/integration/ -v

Skip in CI if no Postgres available:
  pytest tests/ --ignore=tests/integration/
"""

import os
import uuid
from datetime import datetime, timezone

import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

# Ensure encryption key is set before importing api modules
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())

from api.database import Base  # noqa: E402

INTEGRATION_DB_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql:///workout_planner_test"
)
ADMIN_DB_URL = "postgresql:///postgres"


# ─── Session-scoped: create DB + run migrations once per test run ─────────────

@pytest.fixture(scope="session")
def pg_engine():
    """
    Create the test database if needed, run Alembic migrations,
    yield the engine, then downgrade (drop all tables) on teardown.
    """
    # Create DB if it doesn't exist
    admin = create_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'workout_planner_test'")
        ).fetchone()
        if not exists:
            conn.execute(text("CREATE DATABASE workout_planner_test"))
    admin.dispose()

    # Run migrations
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", INTEGRATION_DB_URL)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(INTEGRATION_DB_URL, poolclass=NullPool)
    yield engine

    # Teardown — drop all tables so next run starts clean
    command.downgrade(alembic_cfg, "base")
    engine.dispose()


# ─── Function-scoped: truncate all data between tests ─────────────────────────

@pytest.fixture(autouse=True)
def clean_tables(pg_engine):
    """Truncate all data after each test. Schema (tables) is preserved."""
    yield
    with pg_engine.connect() as conn:
        conn.execute(text(
            "TRUNCATE TABLE user_credentials, program_history, classifications, "
            "schedules, videos, user_channels, channels, users RESTART IDENTITY CASCADE"
        ))
        conn.commit()


@pytest.fixture
def db_session(pg_engine):
    """Yield a SQLAlchemy 2.x Session backed by the real PostgreSQL test DB."""
    SessionFactory = sessionmaker(bind=pg_engine)
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


# ─── Data helpers ─────────────────────────────────────────────────────────────

@pytest.fixture
def make_user(db_session):
    """Factory fixture — creates and returns a persisted User."""
    from api.models import User

    def _make(google_id=None, email="test@example.com", display_name="Test User"):
        user = User(
            google_id=google_id or str(uuid.uuid4()),
            email=email,
            display_name=display_name,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make


@pytest.fixture
def auth_client(db_session):
    """
    TestClient wired to the real PostgreSQL session with a pre-authenticated user.
    Returns (client, user).
    """
    from fastapi.testclient import TestClient

    from api.dependencies import get_current_user, get_db
    from api.main import app
    from api.models import User

    user = User(
        google_id="integration-test-google-id",
        email="integration@example.com",
        display_name="Integration User",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    def _override_get_current_user():
        return user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, user

    app.dependency_overrides.clear()


@pytest.fixture
def make_channel(db_session):
    """Factory fixture — creates and returns a persisted Channel with a UserChannel join row."""
    from api.models import Channel, UserChannel

    def _make(user_id, name="TestChannel", youtube_url="https://youtube.com/@test"):
        ch = Channel(
            name=name,
            youtube_url=youtube_url,
            added_at=datetime.now(timezone.utc),
        )
        db_session.add(ch)
        db_session.flush()
        db_session.add(UserChannel(user_id=user_id, channel_id=ch.id))
        db_session.commit()
        db_session.refresh(ch)
        return ch

    return _make
