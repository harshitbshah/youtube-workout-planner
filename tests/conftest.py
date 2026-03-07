import pytest
import src.db as db_module


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Patch DB_PATH to a temp file so tests never touch the production DB."""
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()
