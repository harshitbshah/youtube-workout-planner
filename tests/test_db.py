import src.db as db_module


def test_init_db_creates_tables(test_db):
    with db_module.get_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"videos", "classifications", "program_history"}.issubset(tables)


def test_init_db_idempotent(test_db):
    # Calling init_db() a second time must not raise
    db_module.init_db()
