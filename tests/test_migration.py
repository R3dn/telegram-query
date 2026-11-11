"""Tests for migration.py - the desktop packaging data-migration contract.

These tests enforce the safety rules that the release depends on:
never overwrite, copy-not-move, idempotency, lock handling, and the
empty-archive-only import path.
"""
import json
import os
import sqlite3
import time
from pathlib import Path

import pytest

import config
import db
import migration

# ---------------------------------------------------------------------------
# Helpers: build small realistic archives
# ---------------------------------------------------------------------------

def make_archive(path: Path, messages: int = 3, env: str | None = None,
                 with_session: bool = True) -> Path:
    """A real Telegram Query archive at <path>/ (db + session + .env)."""
    path.mkdir(parents=True, exist_ok=True)
    conn = db.get_db(str(path / migration.DB_NAME))
    try:
        db.upsert_chat(conn, -100123, "Test Group", "testgroup", "group")
        for i in range(messages):
            db.upsert_message(conn, -100123, 1000 + i,
                              f"2026-11-0{i + 1}T10:00:00+00:00",
                              5, "tester",
                              f"hello world {i} عرض")
        conn.commit()
    finally:
        conn.close()
    if with_session:
        (path / migration.SESSION_NAME).write_bytes(b"fake-session-data")
    if env is not None:
        (path / ".env").write_text(env, encoding="utf-8")
    return path


def count_messages(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    finally:
        conn.close()


@pytest.fixture()
def source(tmp_path):
    return make_archive(tmp_path / "source", messages=3)


@pytest.fixture()
def target(tmp_path):
    return tmp_path / "target"


# ---------------------------------------------------------------------------
# Core migration
# ---------------------------------------------------------------------------

def test_migrate_copies_db_session_and_env(source, target):
    env = ("TG_API_ID=111\nTG_API_HASH=xyz\n"
           "TG_DB_PATH=/old/absolute/path.db\nHOST=0.0.0.0\nPORT=9999\n")
    (source / ".env").write_text(env, encoding="utf-8")
    entry = migration.migrate_data(source, target)
    assert entry["status"] == "ok"
    assert count_messages(target / migration.DB_NAME) == 3
    assert (target / migration.SESSION_NAME).read_bytes() == b"fake-session-data"
    # the .env is copied but path-relocation and bind keys are dropped:
    # the migrated install resolves to the canonical data dir and stays
    # loopback. Credentials survive.
    text = (target / ".env").read_text(encoding="utf-8")
    assert "TG_API_ID=111" in text and "TG_API_HASH=xyz" in text
    assert "TG_DB_PATH" not in text and "HOST" not in text
    assert "PORT" not in text
    # the source is a backup - copy, never move
    assert (source / migration.DB_NAME).exists()
    assert (source / migration.SESSION_NAME).exists()
    # report recorded
    report = json.loads((target / "migration-report.json").read_text())
    assert report[0]["source"].endswith("source")


def test_migrate_is_a_copy_never_a_move(source, target):
    before = (source / migration.DB_NAME).stat().st_size
    migration.migrate_data(source, target)
    assert (source / migration.DB_NAME).stat().st_size == before


def test_migrate_never_overwrites_existing_database(source, target):
    make_archive(target, messages=7, with_session=False)
    with pytest.raises(migration.MigrationError, match="already contains"):
        migration.migrate_data(source, target)
    # nothing was touched on either side
    assert count_messages(target / migration.DB_NAME) == 7
    assert count_messages(source / migration.DB_NAME) == 3


def test_migrate_is_idempotent(source, target):
    migration.migrate_data(source, target)
    with pytest.raises(migration.MigrationError, match="already contains"):
        migration.migrate_data(source, target)
    assert count_messages(target / migration.DB_NAME) == 3


def test_migrate_wal_source_is_snapshotted_consistently(source, target):
    # a live source in WAL mode with un-checkpointed data
    conn = sqlite3.connect(source / migration.DB_NAME)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("INSERT INTO messages (chat_id, msg_id, date, sender_id, "
                 "sender_name, text, text_norm, has_media, edited) VALUES "
                 "(-100123, 5, '2026-11-05T12:00:00+00:00', 1, 'w', "
                 "'wal row', 'wal row', 0, 0)")
    conn.commit()
    conn.close()
    migration.migrate_data(source, target)
    assert count_messages(target / migration.DB_NAME) == 4


def test_migrate_missing_db_is_a_clear_error(tmp_path, target):
    (tmp_path / "source").mkdir()
    with pytest.raises(migration.MigrationError, match="No messages.db"):
        migration.migrate_data(tmp_path / "source", target)


def test_migrate_rejects_non_archive(tmp_path, target):
    src = tmp_path / "source"
    src.mkdir()
    (src / migration.DB_NAME).write_bytes(b"not a database at all")
    with pytest.raises(migration.MigrationError,
                       match="not a Telegram Query archive"):
        migration.migrate_data(src, target)


# ---------------------------------------------------------------------------
# Locking
# ---------------------------------------------------------------------------

def test_active_lock_blocks_migration(source, target):
    target.mkdir(parents=True)
    lock = target / ".migration.lock"
    lock.write_text("pid=1\n")
    with pytest.raises(migration.MigrationError, match="Another migration"):
        migration.migrate_data(source, target)
    # nothing was copied
    assert not (target / migration.DB_NAME).exists()


def test_stale_lock_is_taken_over(source, target):
    target.mkdir(parents=True)
    lock = target / ".migration.lock"
    lock.write_text("pid=1\n")
    old = time.time() - migration._LOCK_STALE_SECONDS - 60
    os.utime(lock, (old, old))
    migration.migrate_data(source, target)
    assert (target / migration.DB_NAME).exists()
    assert not lock.exists()       # released on success


# ---------------------------------------------------------------------------
# The in-app import path (replace_empty)
# ---------------------------------------------------------------------------

def test_import_replaces_only_an_empty_archive(source, target):
    make_archive(target, messages=0, with_session=False)   # fresh install
    entry = migration.migrate_data(source, target, replace_empty=True,
                                   env_target=target / ".env")
    assert entry["status"] == "ok"
    assert count_messages(target / migration.DB_NAME) == 3
    # the replaced empty db was backed up first
    backups = list((target / "backups").glob("pre-import-*/"))
    assert len(backups) == 1
    assert (backups[0] / migration.DB_NAME).exists()


def test_import_refuses_a_used_archive(source, target):
    make_archive(target, messages=5, with_session=False)
    with pytest.raises(migration.MigrationError, match="not empty"):
        migration.migrate_data(source, target, replace_empty=True)
    assert count_messages(target / migration.DB_NAME) == 5


def test_import_refuses_when_a_session_exists(source, target):
    target.mkdir(parents=True)
    (target / migration.SESSION_NAME).write_bytes(b"existing session")
    with pytest.raises(migration.MigrationError, match="not empty"):
        migration.migrate_data(source, target, replace_empty=True)
    assert (target / migration.SESSION_NAME).read_bytes() == b"existing session"


def test_archive_is_empty_detection(tmp_path):
    d = tmp_path / "d"
    d.mkdir()

    def is_empty(data: Path) -> bool:
        return migration.archive_is_empty(
            data / migration.DB_NAME,
            config.session_file(data / migration.SESSION_NAME))

    assert is_empty(d) is True                 # no db at all
    make_archive(d, messages=0, with_session=False)
    assert is_empty(d) is True                 # zero messages
    make_archive(d, messages=1, with_session=False)
    assert is_empty(d) is False
    d2 = tmp_path / "d2"
    make_archive(d2, messages=0, with_session=True)
    assert is_empty(d2) is False               # a session counts


# ---------------------------------------------------------------------------
# Auto-migration (startup path)
# ---------------------------------------------------------------------------

def test_auto_migrate_is_a_noop_in_source_runs(source, tmp_path,
                                               monkeypatch):
    monkeypatch.setattr(config, "IS_FROZEN", False)
    assert migration.auto_migrate() is None


def test_auto_migrate_finds_legacy_archive_beside_exe(source, target,
                                                      monkeypatch):
    monkeypatch.setattr(config, "IS_FROZEN", True)
    monkeypatch.setattr(config, "DATA_DIR", target)
    monkeypatch.setattr(config, "INSTALL_DIR", source)
    for env_name in ("TG_DATA_DIR", "TG_DB_PATH", "TG_SESSION_PATH"):
        monkeypatch.delenv(env_name, raising=False)
    assert (target / migration.DB_NAME).exists() is False
    entry = migration.auto_migrate()
    assert entry is not None and entry["status"] == "ok"
    assert count_messages(target / migration.DB_NAME) == 3


def test_auto_migrate_respects_explicit_overrides(source, target,
                                                  monkeypatch):
    monkeypatch.setattr(config, "IS_FROZEN", True)
    monkeypatch.setattr(config, "DATA_DIR", target)
    monkeypatch.setattr(config, "INSTALL_DIR", source)
    monkeypatch.setenv("TG_DATA_DIR", str(target))
    assert migration.auto_migrate() is None
    assert not (target / migration.DB_NAME).exists()
