"""
Pytest fixtures shared across all test modules.

Key design decisions
--------------------
* A file-based SQLite database (created in a temp directory per test session)
  is used so tests are fast, isolated, and avoid in-memory SQLite's
  single-connection limitation that causes issues when multiple sessions are
  open concurrently (route handler + background worker).
* The app's `engine` and `SessionLocal` are replaced before the app is
  imported by any test, ensuring every test uses the test database.
* The background worker's `submit_job` is patched to run synchronously so
  tests can assert on the completed state without polling or sleeping.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── patch database BEFORE importing the app ──────────────────────────────────
import app.database as _db_module

# Use a temp file-based SQLite so multiple sessions work correctly
_tmp_dir = tempfile.mkdtemp()
TEST_DB_PATH = os.path.join(_tmp_dir, "test_certificates.db")
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Replace module-level singletons so every import sees the test engine
_db_module.engine = test_engine
_db_module.SessionLocal = TestSessionLocal

# ── now it is safe to import the app ─────────────────────────────────────────
from app.models import Base
from app.database import get_db
from app.main import app


@pytest.fixture(autouse=True)
def reset_db():
    """Drop and recreate all tables before each test for isolation."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db_session():
    """Yield a raw SQLAlchemy session for direct DB inspection in tests."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(monkeypatch):
    """
    Return a TestClient wired to the test database.

    The worker's submit_job is patched to execute synchronously inside the
    same thread, so tests see a fully processed job immediately.
    """
    import app.worker as worker_module
    import app.routers.jobs as jobs_router_module

    def _sync_submit(job_id: str, db_factory):
        """Run the worker synchronously (blocking) for test predictability."""
        worker_module._process_job(job_id, TestSessionLocal)

    # Patch the name in the router module (where it was imported to)
    monkeypatch.setattr(jobs_router_module, "submit_job", _sync_submit)
    # Also patch the worker module for tests that call worker directly
    monkeypatch.setattr(worker_module, "submit_job", _sync_submit)

    # Override the DB dependency to use the test session factory
    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

VALID_JOB_PAYLOAD = {
    "event_name": "Python Masterclass 2024",
    "issued_by": "Acme Academy",
    "issue_date": "2024-11-15",
    "recipients": [
        {"name": "Alice Smith", "email": "alice@example.com"},
        {"name": "Bob Jones", "email": "bob@example.com"},
    ],
}
