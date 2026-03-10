"""
test_schema.py — Verify Alembic migrations produce the correct schema.

These tests catch migration bugs that SQLite unit tests never would:
  - Missing tables or columns
  - Wrong column types
  - Missing constraints
  - Alembic version tracking
"""

from sqlalchemy import inspect, text


def test_all_tables_exist(pg_engine):
    inspector = inspect(pg_engine)
    tables = set(inspector.get_table_names())
    expected = {
        "users", "channels", "videos", "classifications",
        "schedules", "program_history", "user_credentials", "alembic_version",
    }
    assert expected.issubset(tables)


def test_alembic_version_is_current(pg_engine):
    with pg_engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "003"


def test_users_columns(pg_engine):
    inspector = inspect(pg_engine)
    columns = {c["name"]: c for c in inspector.get_columns("users")}
    assert "id" in columns
    assert "google_id" in columns
    assert "email" in columns
    assert "display_name" in columns
    assert "created_at" in columns


def test_users_google_id_unique_constraint(pg_engine):
    inspector = inspect(pg_engine)
    unique_constraints = inspector.get_unique_constraints("users")
    unique_cols = [col for uc in unique_constraints for col in uc["column_names"]]
    # google_id must be unique — enforced at DB level
    assert "google_id" in unique_cols


def test_channels_foreign_key_to_users(pg_engine):
    inspector = inspect(pg_engine)
    fks = inspector.get_foreign_keys("channels")
    fk_cols = [fk["constrained_columns"][0] for fk in fks]
    assert "user_id" in fk_cols


def test_videos_foreign_key_to_channels(pg_engine):
    inspector = inspect(pg_engine)
    fks = inspector.get_foreign_keys("videos")
    fk_cols = [fk["constrained_columns"][0] for fk in fks]
    assert "channel_id" in fk_cols


def test_classifications_foreign_key_to_videos(pg_engine):
    inspector = inspect(pg_engine)
    fks = inspector.get_foreign_keys("classifications")
    fk_cols = [fk["constrained_columns"][0] for fk in fks]
    assert "video_id" in fk_cols


def test_program_history_has_date_column(pg_engine):
    """week_start must be DATE type in PostgreSQL — not a string."""
    inspector = inspect(pg_engine)
    columns = {c["name"]: c for c in inspector.get_columns("program_history")}
    assert "week_start" in columns
    # SQLAlchemy reflects PostgreSQL DATE as DATE type
    assert "DATE" in str(columns["week_start"]["type"]).upper()


def test_user_credentials_columns(pg_engine):
    inspector = inspect(pg_engine)
    columns = {c["name"] for c in inspector.get_columns("user_credentials")}
    assert {
        "user_id", "youtube_refresh_token", "anthropic_key",
        "updated_at", "credentials_valid", "youtube_playlist_id",
    }.issubset(columns)
