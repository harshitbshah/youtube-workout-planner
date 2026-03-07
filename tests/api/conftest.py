"""
Test fixtures for the FastAPI layer.

Uses SQLite in-memory so tests never touch PostgreSQL.
The get_db dependency is overridden to use the test DB session.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.database import Base
from api.dependencies import get_db
from api.main import app

TEST_DATABASE_URL = "sqlite://"

# StaticPool ensures all connections share the same in-memory SQLite DB,
# so tables created in one connection are visible in all others.
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function", autouse=True)
def _reset_db():
    """Re-create all tables before each test so state is clean."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Yield a SQLAlchemy session backed by the in-memory SQLite test DB."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """TestClient with get_db overridden to use the test session."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass  # session closed by db_session fixture

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()
