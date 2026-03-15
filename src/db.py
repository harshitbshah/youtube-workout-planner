"""
db.py - SQLite database setup and operations.
All video library, classification, and history data lives here.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "workout_library.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS videos (
                id          TEXT PRIMARY KEY,
                channel_id  TEXT NOT NULL,
                channel_name TEXT NOT NULL,
                title       TEXT NOT NULL,
                description TEXT,
                duration_sec INTEGER,
                published_at TEXT,
                url         TEXT NOT NULL,
                tags        TEXT
            );

            CREATE TABLE IF NOT EXISTS classifications (
                video_id        TEXT PRIMARY KEY REFERENCES videos(id),
                workout_type    TEXT,   -- HIIT | Strength | Mobility | Cardio | Other
                body_focus      TEXT,   -- upper | lower | full | core | any
                difficulty      TEXT,   -- beginner | intermediate | advanced
                has_warmup      INTEGER,  -- 0 or 1
                has_cooldown    INTEGER,  -- 0 or 1
                classified_at   TEXT
            );

            CREATE TABLE IF NOT EXISTS program_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start      TEXT NOT NULL,
                video_id        TEXT REFERENCES videos(id),
                assigned_day    TEXT NOT NULL,
                completed       INTEGER DEFAULT 0
            );
        """)


# ── To be implemented in scanner.py, classifier.py, planner.py ──
