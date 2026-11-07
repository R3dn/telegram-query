"""Test configuration: isolate Telegram Query into a temp environment.

Env vars are set BEFORE importing the app modules so config.settings
resolves to the temp paths. One DB serves the whole session; API tests
clear it per-test.
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="tgq-test-")
os.environ["TG_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ["TG_SESSION_PATH"] = os.path.join(_TMP, "session")
os.environ["TG_API_ID"] = "123456"
os.environ["TG_API_HASH"] = "testhash"
os.environ["AI_API_KEY"] = "test-ai-key"
os.environ["AI_BASE_URL"] = "http://localhost:1/v1"
os.environ["AI_MODEL"] = "test-model"
os.environ["HOST"] = "127.0.0.1"

import pytest  # noqa: E402

import db  # noqa: E402  (must come after env setup)


@pytest.fixture()
def conn(tmp_path):
    """A clean connection on a fresh per-test database."""
    c = db.get_db(str(tmp_path / "test.db"))
    yield c
    c.close()


@pytest.fixture()
def api_client():
    """FastAPI TestClient bound to the session DB, cleared per test."""
    from fastapi.testclient import TestClient

    import app as app_module

    c = db.get_db()
    try:
        c.execute("DELETE FROM messages")
        c.execute("DELETE FROM chats")
        c.execute("DELETE FROM bookmarks")
        c.execute("DELETE FROM saved_searches")
        # NOTE: DELETE FROM an external-content FTS table is a no-op -
        # rebuild the index instead, or stale entries resurface once the
        # content table reuses rowids (cross-test contamination).
        db.reindex_fts(c)
        c.commit()
    finally:
        c.close()

    # reset job state between tests
    from jobs import JOBS
    JOBS.running = False
    JOBS.name = ""
    JOBS.queue.clear()
    JOBS.last_done = None
    import sync
    sync.CANCEL.clear()

    with TestClient(app_module.app) as client:
        yield client
