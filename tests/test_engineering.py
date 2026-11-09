"""v9 engineering hardening tests: search restructure semantics, ingest
fast path, ANALYZE maintenance, readiness, provider-client caching +
concurrency guard, sync failure propagation, and the groups rewrite.

Every test here pins a behavior that the performance work touched, so
the optimizations can never silently change results.
"""
import sqlite3
import threading

import pytest

import ai
import config
import db

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _seed_archive(conn, n=30, chat_ids=(-1, -2)):
    """Deterministic small archive: each chat gets n messages, every 3rd
    mentions 'offer' so search has a realistic hit rate."""
    for cid in chat_ids:
        db.upsert_chat(conn, cid, f"G{abs(cid)}", None, "group")
    i = 0
    for cid in chat_ids:
        for k in range(1, n + 1):
            text = f"offer number {k} in {cid}" if k % 3 == 0 else \
                f"regular chatter {k} in {cid}"
            db.upsert_message(conn, cid, k, f"2026-01-{(k % 28) + 1:02d}T10:00:00",
                              i, f"sender_{i % 5}", text)
            i += 1
    conn.commit()


# ---------------------------------------------------------------------------
# search(): restructured ranking must keep exact semantics
# ---------------------------------------------------------------------------

def test_search_respects_limit_and_orders_by_rank(conn):
    _seed_archive(conn, n=60)
    rows = db.search(conn, ["offer"], require_all=False, limit=5)
    assert len(rows) == 5
    ranks = [r["rank"] for r in rows]
    assert ranks == sorted(ranks), "must stay best-rank-first"
    assert all("offer" in r["text"] for r in rows)


def test_search_excludes_untracked_even_when_outranking(conn):
    """The rank subquery must not let untracked-chat messages consume the
    LIMIT: tracked hits must fill it."""
    _seed_archive(conn, n=6, chat_ids=(-1, -2))
    db.upsert_chat(conn, -3, "Untracked", None, "group", tracked=0)
    for k in range(1, 21):   # 20 hits in the untracked chat
        db.upsert_message(conn, -3, k, "2026-01-01T00:00:00", 1, "x",
                          f"offer only in untracked {k}")
    conn.commit()
    rows = db.search(conn, ["offer"], require_all=False, limit=200)
    assert rows, "tracked chats have hits"
    assert all(r["chat_id"] != -3 for r in rows), \
        "untracked messages must never surface"


def test_search_filters_apply_before_rank_limit(conn):
    """A filter must narrow the ranked set (top-N of the FILTERED rows),
    exactly like the pre-v9 query shape did."""
    _seed_archive(conn, n=30)
    rows = db.search(conn, ["offer"], require_all=False, limit=200,
                    chat_ids=[-1])
    assert rows and all(r["chat_id"] == -1 for r in rows)
    # date filter
    rows = db.search(conn, ["offer"], require_all=False, limit=200,
                     date_from="2026-01-05", date_to="2026-01-10")
    assert rows and all("2026-01-05" <= r["date"][:10] <= "2026-01-10"
                        for r in rows)
    # sender filter
    rows = db.search(conn, ["offer"], require_all=False, limit=200,
                     sender="sender_0")
    assert rows and all(r["sender_name"] == "sender_0" for r in rows)
    # min_msg_id (incremental pipelines)
    rows = db.search(conn, ["offer"], require_all=False, limit=200,
                     min_msg_id=25)
    assert rows and all(r["msg_id"] > 25 for r in rows)


def test_search_bookmarked_filter(conn):
    _seed_archive(conn, n=9)
    conn.execute("INSERT INTO bookmarks (chat_id, msg_id, note, created_at, "
                 "updated_at) VALUES (-1, 3, '', 'x', 'x')")
    conn.commit()
    rows = db.search(conn, ["offer"], require_all=False, bookmarked=True)
    assert len(rows) == 1 and rows[0]["msg_id"] == 3
    assert rows[0]["bookmarked"] == 1


def test_search_min_msg_id_and_bookmark_note_columns_survive(conn):
    _seed_archive(conn, n=9)
    conn.execute("INSERT INTO bookmarks (chat_id, msg_id, note, created_at, "
                 "updated_at) VALUES (-1, 3, 'note here', 'x', 'x')")
    conn.commit()
    row = db.search(conn, ["offer number 3"], require_all=False,
                    chat_ids=[-1])[0]
    assert row["bookmark_note"] == "note here"
    assert "chat_title" in row and row["chat_title"] == "G1"


# ---------------------------------------------------------------------------
# search_diverse(): round-robin must match the old per-chat interleave
# ---------------------------------------------------------------------------

def test_search_diverse_interleaves_chats(conn):
    _seed_archive(conn, n=30)
    rows = db.search_diverse(conn, ["offer"], limit=6)
    assert len(rows) == 6
    chats = [r["chat_id"] for r in rows]
    # round-robin: first position of every chat before any second position
    assert chats[0] != chats[1], "two different chats must lead"
    assert len(set(chats)) == 2
    # and each chat's rows stay in rank order within their own subsequence
    for cid in (-1, -2):
        sub = [r["rank"] for r in rows if r["chat_id"] == cid]
        assert sub == sorted(sub)


# ---------------------------------------------------------------------------
# browse(): text_norm dropped from the payload, everything else intact
# ---------------------------------------------------------------------------

def test_browse_omits_text_norm_and_keeps_rows(conn):
    _seed_archive(conn, n=12)
    rows, cursor, more = db.browse(conn, limit=5)
    assert len(rows) == 5
    for r in rows:
        assert "text_norm" not in r, "payload must not carry text_norm"
        assert r["text"] and "chat_title" in r


# ---------------------------------------------------------------------------
# upsert_message(): fast path must keep the FTS index exactly right
# ---------------------------------------------------------------------------

def test_upsert_new_message_is_searchable(conn):
    db.upsert_chat(conn, -1, "G", None, "group")
    db.upsert_message(conn, -1, 1, "2026-01-01T00:00:00", 1, "a",
                      "fresh solar panel deal")
    conn.commit()
    assert db.search(conn, ["solar panel"])


def test_upsert_edit_updates_fts_and_drops_old_text(conn):
    db.upsert_chat(conn, -1, "G", None, "group")
    db.upsert_message(conn, -1, 1, "2026-01-01T00:00:00", 1, "a",
                      "old laptop price")
    conn.commit()
    db.upsert_message(conn, -1, 1, "2026-01-02T00:00:00", 1, "a",
                      "new desktop price", edited=1)
    conn.commit()
    assert not db.search(conn, ["laptop"]), "old text must leave the index"
    hits = db.search(conn, ["desktop"])
    assert hits and hits[0]["edited"] == 1


def test_upsert_unchanged_rescan_does_not_duplicate_fts(conn):
    db.upsert_chat(conn, -1, "G", None, "group")
    db.upsert_message(conn, -1, 1, "2026-01-01T00:00:00", 1, "a",
                      "stable content here")
    conn.commit()
    before = conn.execute(
        "SELECT COUNT(*) c FROM messages_fts").fetchone()["c"]
    # day-rescan re-fetches the identical message
    db.upsert_message(conn, -1, 1, "2026-01-01T00:00:00", 1, "a",
                      "stable content here")
    conn.commit()
    after = conn.execute(
        "SELECT COUNT(*) c FROM messages_fts").fetchone()["c"]
    assert before == after, "identical text must not churn the index"
    assert len(db.search(conn, ["stable content"])) == 1


# ---------------------------------------------------------------------------
# groups endpoint: correlated-subquery rewrite returns identical values
# ---------------------------------------------------------------------------

def test_groups_counts_match_bruteforce(conn):
    """The correlated-subquery rewrite must return the same values the
    old JOIN+GROUP BY did (verified against a literal count)."""
    _seed_archive(conn, n=12)
    # one chat with zero messages must read 0 / None
    db.upsert_chat(conn, -9, "Empty", None, "group")
    conn.commit()
    n = conn.execute("SELECT COUNT(*) c FROM messages WHERE chat_id=-1"
                     ).fetchone()["c"]
    rows, _, _ = db.browse(conn, chat_ids=[-1], limit=200)
    assert n == 12 and len(rows) == 12

    # and the endpoint reads the same numbers from the session DB
    sconn = db.get_db()
    try:
        _seed_archive(sconn, n=12)
        db.upsert_chat(sconn, -9, "Empty", None, "group")
        sconn.commit()
        from fastapi.testclient import TestClient

        import app as app_module
        with TestClient(app_module.app) as client:
            r = client.get("/api/groups")
            assert r.status_code == 200
            by_id = {g["chat_id"]: g for g in r.json()}
            assert by_id[-1]["message_count"] == 12
            assert by_id[-2]["message_count"] == 12
            assert by_id[-9]["message_count"] == 0
            assert by_id[-9]["last_message"] is None
    finally:
        sconn.close()


# ---------------------------------------------------------------------------
# ANALYZE maintenance hook
# ---------------------------------------------------------------------------

def test_analyze_if_stale_threshold(conn):
    _seed_archive(conn, n=10)   # 20 messages
    # growth floor: doubling is satisfied but 20 messages of growth is not
    db.set_setting(conn, "analyze_count", "5")
    conn.commit()
    assert db.analyze_if_stale(conn) is False
    assert conn.execute(
        "SELECT value FROM app_settings WHERE key='analyze_count'"
    ).fetchone()["value"] == "5", "a no-op must not move the marker"

    # real growth: cross the 5000-message floor, then it runs once and
    # records the new count
    for i in range(5001):
        db.upsert_message(conn, -1, 1000 + i, "2026-02-01T00:00:00",
                          1, "bulk", f"bulk message {i}")
    conn.commit()
    assert db.analyze_if_stale(conn) is True
    assert conn.execute(
        "SELECT value FROM app_settings WHERE key='analyze_count'"
    ).fetchone()["value"] == str(20 + 5001)
    # immediately re-running is a no-op (must double again)
    assert db.analyze_if_stale(conn) is False


def test_analyze_hook_zero_arg_form(conn):
    """Registered in POST_SYNC_HOOKS: must be callable with no args."""
    _seed_archive(conn, n=10)
    db.set_setting(conn, "analyze_count", "0")
    conn.commit()
    # growth floor blocks on small archives (by design)
    assert db.analyze_if_stale() is False


# ---------------------------------------------------------------------------
# readiness endpoint
# ---------------------------------------------------------------------------

def test_readiness_reports_db_and_never_fails_on_optional_deps(api_client):
    r = api_client.get("/api/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["checks"]["db"] is True
    # optional dependencies are informational only
    assert "telegram_configured" in body and "ai_configured" in body


def test_liveness_touches_nothing(api_client):
    r = api_client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True


# ---------------------------------------------------------------------------
# AI provider client: caching + invalidation + concurrency guard
# ---------------------------------------------------------------------------

class _FakeResp:
    class _Msg:
        class _M:
            content = "ok"
        message = _M()
    class _U:
        prompt_tokens = 3
        completion_tokens = 2
    choices = [_Msg()]
    usage = _U()


def test_client_cached_until_settings_change(monkeypatch):
    made = []

    class FakeOpenAI:
        def __init__(self, api_key=None, base_url=None, timeout=None):
            made.append((api_key, base_url))
            self.api_key = api_key

    monkeypatch.setattr(ai, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(config.settings, "ai_api_key", "key1", raising=False)
    monkeypatch.setattr(config.settings, "ai_base_url", "http://x/v1", raising=False)

    c1 = ai.get_client()
    c2 = ai.get_client()
    assert c1 is c2 and len(made) == 1, "client must be reused"

    # settings change (setup wizard) -> new client
    monkeypatch.setattr(config.settings, "ai_api_key", "key2", raising=False)
    c3 = ai.get_client()
    assert c3 is not c1 and made[-1][0] == "key2"


def test_provider_slot_bounds_concurrency():
    """Two threads must serialize through the semaphore when size=1."""
    import os
    old = os.environ.get("TGQ_AI_MAX_CONCURRENCY")
    os.environ["TGQ_AI_MAX_CONCURRENCY"] = "1"
    try:
        config.settings.ai_max_concurrency = 1
        active = 0
        peak = 0
        lock = threading.Lock()

        def work():
            nonlocal active, peak
            with ai._provider_slot():
                with lock:
                    active += 1
                    peak = max(peak, active)
                import time
                time.sleep(0.05)
                with lock:
                    active -= 1

        threads = [threading.Thread(target=work) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert peak == 1, "semaphore must serialize concurrent provider calls"
    finally:
        if old is None:
            os.environ.pop("TGQ_AI_MAX_CONCURRENCY", None)
        else:
            os.environ["TGQ_AI_MAX_CONCURRENCY"] = old
        config.settings.ai_max_concurrency = 4


def test_busy_provider_maps_to_503(api_client, monkeypatch):

    class Busy:
        def __init__(self, *_a, **_k):
            pass

    def raise_busy(*_a, **_k):
        raise ai.AIBusyError("The AI layer is busy")

    monkeypatch.setattr(ai, "get_client", lambda: Busy())
    monkeypatch.setattr(ai, "_chat", raise_busy)
    r = api_client.post("/api/ask", json={"question": "anything"})
    assert r.status_code == 503
    assert "busy" in r.json()["error"].lower()


# ---------------------------------------------------------------------------
# sync failure propagation
# ---------------------------------------------------------------------------

def test_all_chats_failed_raises_honest_error(monkeypatch):
    import sync

    class DeadClient:
        async def get_entity(self, chat_id):
            raise RuntimeError("unreachable")
        async def get_me(self):
            return type("Me", (), {"first_name": "tester"})()
        async def disconnect(self):
            pass

    async def fake_connect(client, interactive):
        return client

    monkeypatch.setattr(sync, "make_client", lambda *a, **k: DeadClient())
    monkeypatch.setattr(sync, "connect_client", fake_connect)
    monkeypatch.setattr(sync, "need_creds", lambda: None)
    monkeypatch.setattr(sync, "_app_running", lambda: False)

    # seed the session DB (sync.run opens the configured database)
    conn = db.get_db()
    try:
        conn.execute("DELETE FROM chats")
        db.upsert_chat(conn, -1, "OnlyChat", None, "group")
        conn.commit()
    finally:
        conn.close()

    import asyncio
    args = sync.SyncArgs(login_interactive=False)
    try:
        with pytest.raises(RuntimeError, match="failed to sync"):
            asyncio.run(sync.run(args))
    finally:
        conn = db.get_db()
        try:
            conn.execute("DELETE FROM chats WHERE chat_id=-1")
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# migration v9
# ---------------------------------------------------------------------------

def test_v9_indexes_exist_on_fresh_db(conn):
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}
    assert "idx_messages_chat_sender" in names
    assert "idx_messages_reply" in names
    assert "idx_messages_date_id" in names
    assert "idx_messages_date" not in names, \
        "replaced by the prefix-compatible composite"


def test_v9_upgrade_from_older_db(tmp_path):
    """A schema-v5 database upgrades to v9 with the new indexes."""
    path = str(tmp_path / "old.db")
    c = sqlite3.connect(path)
    c.executescript("""
        CREATE TABLE chats (
            chat_id INTEGER PRIMARY KEY, title TEXT NOT NULL,
            username TEXT, kind TEXT NOT NULL DEFAULT 'group',
            last_msg_id INTEGER NOT NULL DEFAULT 0, last_synced TEXT,
            tracked INTEGER NOT NULL DEFAULT 1,
            backfill_floor INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE messages (
            chat_id INTEGER NOT NULL, msg_id INTEGER NOT NULL,
            date TEXT NOT NULL, sender_id INTEGER, sender_name TEXT,
            text TEXT NOT NULL DEFAULT '',
            text_norm TEXT NOT NULL DEFAULT '',
            has_media INTEGER NOT NULL DEFAULT 0,
            edited INTEGER NOT NULL DEFAULT 0, reply_to INTEGER,
            PRIMARY KEY (chat_id, msg_id));
        CREATE VIRTUAL TABLE messages_fts USING fts5(
            text_norm, content='messages', content_rowid='rowid',
            tokenize='trigram');
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta VALUES ('version', '5');
        INSERT INTO chats VALUES (-1, 'Old', NULL, 'group', 5, NULL, 1, 0);
        INSERT INTO messages VALUES
            (-1, 5, '2026-01-01T00:00:00', 1, 'a', 'hello world',
             'hello world', 0, 0, NULL);
        INSERT INTO messages_fts(rowid, text_norm)
            VALUES (1, 'hello world');
    """)
    c.commit()
    c.close()

    db.init_db(path)   # runs SCHEMA + migrations
    conn = db.get_db(path)
    try:
        ver = conn.execute(
            "SELECT value FROM schema_meta WHERE key='version'").fetchone()
        assert ver["value"] == str(db.SCHEMA_VERSION)
        names = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        assert "idx_messages_chat_sender" in names
        assert "idx_messages_reply" in names
        assert "idx_messages_date_id" in names
        assert "idx_messages_date" not in names
        # data preserved and still searchable
        assert db.search(conn, ["hello world"])
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# backups
# ---------------------------------------------------------------------------

def test_backup_script_produces_restorable_snapshot(tmp_path):
    from scripts.backup_db import backup as backup_db  # noqa: TID252
    src = tmp_path / "src.db"
    conn = db.get_db(str(src))
    _seed_archive(conn, n=5)
    conn.close()
    target = backup_db(src, tmp_path / "backups", keep=3)
    assert target.exists()
    # restorable: open it and read
    rconn = sqlite3.connect(target)
    try:
        n = rconn.execute("SELECT COUNT(*) c FROM messages").fetchone()[0]
        assert n == 10
    finally:
        rconn.close()
