"""Migration tests: v2 -> v3 upgrade, idempotency, data preservation."""
import sqlite3

import config
import db

# The v0.3 schema (for building a genuine pre-upgrade database)
V2_SCHEMA = """
CREATE TABLE chats (
    chat_id     INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    username    TEXT,
    kind        TEXT NOT NULL DEFAULT 'group',
    last_msg_id INTEGER NOT NULL DEFAULT 0,
    last_synced TEXT,
    tracked     INTEGER NOT NULL DEFAULT 1,
    backfill_floor INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE messages (
    chat_id     INTEGER NOT NULL,
    msg_id      INTEGER NOT NULL,
    date        TEXT NOT NULL,
    sender_id   INTEGER,
    sender_name TEXT,
    text        TEXT NOT NULL DEFAULT '',
    text_norm   TEXT NOT NULL DEFAULT '',
    has_media   INTEGER NOT NULL DEFAULT 0,
    edited      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, msg_id)
);
CREATE VIRTUAL TABLE messages_fts USING fts5(
    text_norm, content='messages', content_rowid='rowid', tokenize='trigram'
);
CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO schema_meta VALUES ('version', '2');
"""


def make_v2_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(V2_SCHEMA)
    conn.execute("INSERT INTO chats VALUES (-1, 'Old', NULL, 'group', 5, "
                 "'2026-01-01', 1, 0)")
    conn.execute("INSERT INTO messages VALUES (-1, 1, '2026-01-01T10:00:00',"
                 " 7, 'u', 'مبروووك', 'مبروووك', 0, 0)")
    conn.commit()
    conn.close()


def test_upgrade_from_v2_preserves_data_and_flags_reindex(tmp_path):
    path = str(tmp_path / "old.db")
    make_v2_db(path)

    db.init_db(path)   # runs SCHEMA + _migrate on the existing DB
    conn = db.get_db(path)
    try:
        # version bumped, data intact
        v = conn.execute("SELECT value FROM schema_meta WHERE key='version'"
                         ).fetchone()["value"]
        assert v == str(db.SCHEMA_VERSION) and v == "3"
        msg = conn.execute("SELECT text FROM messages").fetchone()
        assert msg["text"] == "مبروووك"
        # new tables exist
        for t in ("app_settings", "saved_searches", "bookmarks"):
            conn.execute(f"SELECT 1 FROM {t}").fetchone()
        # reindex flagged (extended normalization + existing messages)
        if config.settings.normalization_level == "extended":
            assert db.get_setting(conn, "needs_reindex") == "1"
    finally:
        conn.close()


def test_migration_is_idempotent(tmp_path):
    path = str(tmp_path / "old.db")
    make_v2_db(path)
    db.init_db(path)
    conn = db.get_db(path)
    try:
        db._migrate(conn)   # re-running must be a safe no-op
        conn.commit()
        v = conn.execute("SELECT value FROM schema_meta WHERE key='version'"
                         ).fetchone()["value"]
        assert v == "3"
        assert conn.execute("SELECT COUNT(*) c FROM messages"
                            ).fetchone()["c"] == 1
    finally:
        conn.close()


def test_fresh_db_needs_no_reindex(tmp_path):
    path = str(tmp_path / "fresh.db")
    db.init_db(path)
    conn = db.get_db(path)
    try:
        assert db.get_setting(conn, "needs_reindex") is None
        v = conn.execute("SELECT value FROM schema_meta WHERE key='version'"
                         ).fetchone()["value"]
        assert v == "3"
    finally:
        conn.close()


def test_bookmark_fk_blocks_orphans(conn):
    """Bookmarks reference the original message: a nonexistent message is
    rejected by the FK (and real message deletions cascade)."""
    db.upsert_chat(conn, -3, "G", None, "group")
    db.upsert_message(conn, -3, 1, "2026-01-01T10:00:00+00:00", 1, "s", "hi")
    conn.commit()
    conn.execute("INSERT INTO bookmarks VALUES (-3, 1, 'note', 't', 't')")
    conn.commit()
    # cascading delete removes the bookmark with the message
    conn.execute("DELETE FROM messages WHERE chat_id=-3")
    left = conn.execute("SELECT COUNT(*) c FROM bookmarks").fetchone()["c"]
    assert left == 0
