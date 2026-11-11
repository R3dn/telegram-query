"""Safe user-data migration for Telegram Query desktop packaging.

Two entry points:

``auto_migrate()``
    Runs at packaged-app startup, BEFORE the database is opened. Detects a
    legacy source-style archive sitting next to the installed executable
    (the "I used to run this from a checkout" case) and copies it into the
    canonical user-data directory.

``migrate_data(source, target, ...)``
    The core routine, also used by the in-app importer
    (``POST /api/data/import``) so users can point the fresh install at
    any existing archive folder.

Safety contract (all requirements are enforced here, not by callers):

* COPY, never move - the source archive is left exactly where it was.
  The source doubles as the recoverable backup.
* Never silently overwrite: a conflict is a hard error naming both paths.
  The in-app import path may only replace a *confirmed empty* target
  archive, and even then the replaced files are backed up first.
* Idempotent: a successful migration is a no-op on re-run; an interrupted
  one resumes cleanly (staging is scratch, files land atomically in a
  defined order - settings, session, database LAST - so any interruption
  leaves the target either empty-ish or complete, never half-written).
* Interrupted runs are guarded by a lock file with stale detection.
* Everything is logged and recorded in ``migration-report.json``.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import config

log = logging.getLogger("tgq.migration")

DB_NAME = "messages.db"
SESSION_NAME = "tg_session.session"
ENV_NAME = ".env"

_LOCK_NAME = ".migration.lock"
_STAGING_NAME = ".migration-staging"
_LOCK_STALE_SECONDS = 15 * 60          # a lock older than this is stale
_REPLACE_BACKUP_PREFIX = "pre-import-"


class MigrationError(Exception):
    """User-facing migration failure. The message is safe to show."""


@dataclass
class MigrationReport:
    source: str
    target: str
    files: dict = field(default_factory=dict)     # name -> bytes copied
    started: str = ""
    finished: str = ""
    status: str = "ok"                            # ok | skipped | error
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "source": self.source, "target": self.target,
            "files": self.files, "started": self.started,
            "finished": self.finished, "status": self.status,
            "note": self.note,
        }


# ---------------------------------------------------------------------------
# Locking (crash/stale tolerant)
# ---------------------------------------------------------------------------

def _lock_alive(lock: Path) -> bool:
    try:
        age = time.time() - lock.stat().st_mtime
    except OSError:
        return False
    return age < _LOCK_STALE_SECONDS


class _Lock:
    """Best-effort advisory lock; a stale lock is taken over."""

    def __init__(self, data_dir: Path):
        self.path = data_dir / _LOCK_NAME
        self.held = False

    def __enter__(self):
        if _lock_alive(self.path):
            raise MigrationError(
                "Another migration appears to be running (started within the "
                f"last {_LOCK_STALE_SECONDS // 60} minutes). If you are sure "
                "it finished, delete: " + str(self.path))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            f"pid={os.getpid()} at={datetime.now(timezone.utc).isoformat()}\n",
            encoding="utf-8")
        self.held = True
        return self

    def __exit__(self, *exc):
        if self.held:
            try:
                self.path.unlink()
            except OSError:
                pass
        return False


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _open_readonly(path: Path) -> sqlite3.Connection:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def looks_like_archive(db_path: Path) -> bool:
    """True when *db_path* is a readable SQLite file with our schema."""
    try:
        conn = _open_readonly(db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name IN ('messages', 'chats')").fetchone()
            return row is not None
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def archive_is_empty(db_path: Path, session_path: Path) -> bool:
    """True when the archive at *db_path* holds no messages and no
    Telegram session exists at *session_path* - i.e. the archive is
    safe to replace by an import."""
    db_path = Path(db_path)
    if config.session_file(Path(session_path)).exists():
        return False
    if not db_path.exists():
        return True
    try:
        conn = _open_readonly(db_path)
        try:
            row = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()
            return (row["c"] if row else 0) == 0
        finally:
            conn.close()
    except sqlite3.Error:
        return False   # unreadable is not "empty" - refuse to replace


# ---------------------------------------------------------------------------
# Core copy machinery
# ---------------------------------------------------------------------------

def _snapshot_database(src: Path, dst: Path) -> int:
    """Consistent copy of a (possibly WAL-mode, possibly in use) SQLite
    database using SQLite's own backup API - no -wal/-shm juggling, no
    torn reads. Returns the size copied."""
    src_conn = _open_readonly(src)
    try:
        dst_conn = sqlite3.connect(dst)
        try:
            src_conn.backup(dst_conn)
            dst_conn.commit()
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    return dst.stat().st_size


def _plain_copy(src: Path, dst: Path) -> int:
    shutil.copy2(src, dst)
    return dst.stat().st_size


def _filtered_env(source_env: Path, dest_env: Path) -> bool:
    """Copy the source ``.env`` to *dest_env*, dropping the path-relocation
    keys (TG_DATA_DIR / TG_DB_PATH / TG_SESSION_PATH / HOST / PORT) so the
    migrated install resolves to the canonical data dir and keeps binding
    loopback. Returns True when a file was written."""
    lines: list[str] = []
    drop = {"tg_data_dir", "tg_db_path", "tg_session_path", "tg_session",
            "host", "port"}
    for line in source_env.read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0].strip().lower() if "=" in line else ""
        if key and key in drop:
            continue
        lines.append(line)
    dest_env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def _append_report(data_dir: Path, entry: dict) -> None:
    """Keep a small history of migrations next to the data (max 5)."""
    report_path = data_dir / "migration-report.json"
    history: list = []
    if report_path.exists():
        try:
            history = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except (OSError, ValueError):
            history = []
    history.append(entry)
    report_path.write_text(
        json.dumps(history[-5:], indent=2, ensure_ascii=False),
        encoding="utf-8")


def migrate_data(source: Path, target: Path, *, replace_empty: bool = False,
                 target_db: Path | None = None,
                 target_session: Path | None = None,
                 env_target: Path | None = None) -> dict:
    """Copy an archive (db + Telegram session + ``.env``) from *source*
    into the user-data directory *target*.

    ``target_db`` / ``target_session`` / ``env_target`` override the
    default canonical paths (``<target>/messages.db``,
    ``<target>/tg_session.session``, ``<target>/.env``) - the in-app
    importer passes the *configured* locations (honoring TG_DB_PATH /
    TG_SESSION_PATH), so the migration lands exactly where the app
    actually reads and writes.

    ``replace_empty=True`` (the in-app importer) may only replace a target
    that is confirmed empty (see :func:`archive_is_empty`); the replaced
    files are backed up first. Returns the report dict.
    """
    source = Path(source).expanduser()
    target = Path(target).expanduser()
    source_db = source / DB_NAME
    if not source_db.exists():
        raise MigrationError(f"No {DB_NAME} found in {source}")
    if not looks_like_archive(source_db):
        raise MigrationError(
            f"{source_db} is not a Telegram Query archive database.")

    target.mkdir(parents=True, exist_ok=True)
    target_db = Path(target_db) if target_db is not None \
        else target / DB_NAME
    target_session = (Path(target_session) if target_session is not None
                      else config.session_file(target / SESSION_NAME))
    target_env = Path(env_target) if env_target is not None \
        else target / ENV_NAME

    report = MigrationReport(source=str(source), target=str(target),
                             started=_now())
    with _Lock(target):
        # --- pre-flight: never silently overwrite anything ---------------
        # replace_empty (the in-app importer) may only swap in over a
        # target that is confirmed EMPTY - db with zero messages and no
        # Telegram session - and even then backs the replaced files up.
        may_replace = replace_empty and archive_is_empty(target_db,
                                                        target_session)
        if replace_empty and not may_replace:
            raise MigrationError(
                f"The archive at {target} is not empty. Import is only "
                "possible into an empty archive - erase the current data "
                "first (Settings). Nothing was copied.")
        if target_db.exists() and not may_replace:
            raise MigrationError(
                f"{target} already contains a {DB_NAME}. The archive was "
                "NOT copied - nothing was overwritten.")
        if target_session.exists() and not may_replace:
            raise MigrationError(
                f"{target} already contains a Telegram session "
                f"({target_session.name}). The archive was NOT copied.")
        if may_replace and (target_db.exists() or target_session.exists()):
            backup_dir = _backup_target(target, target_db, target_session,
                                        target_env, report)
            report.note = (f"replaced an empty archive; replaced files "
                           f"backed up to {backup_dir}")

        # --- stage everything, then land files atomically -----------------
        staging = target / _STAGING_NAME
        if staging.exists():
            shutil.rmtree(staging)      # scratch from an interrupted run
        staging.mkdir(parents=True)

        # Session (+ its journal, so a crashed writer can still recover)
        session_src = config.session_file(source / SESSION_NAME)
        session_copied = False
        if session_src.exists():
            shutil.copy2(session_src, staging / session_src.name)
            session_copied = True
            journal = session_src.with_name(session_src.name + "-journal")
            if journal.exists():
                shutil.copy2(journal, staging / journal.name)

        # Settings (path-relocation keys are stripped; see _filtered_env)
        env_src = source / ENV_NAME
        have_env = env_src.exists()
        if have_env:
            _filtered_env(env_src, staging / ENV_NAME)

        # Database: consistent snapshot via the backup API. This is the
        # last file to land - an interruption before this point leaves the
        # target still "empty" and the run simply idempotently re-runs.
        staged_db = staging / DB_NAME
        try:
            report.files[DB_NAME] = _snapshot_database(source_db, staged_db)
        except sqlite3.Error as e:
            log.warning("backup-API snapshot failed (%s); falling back to a "
                        "plain file copy", e)
            report.files[DB_NAME] = _plain_copy(source_db, staged_db)
            for suffix in ("-wal", "-shm"):
                side = source_db.with_name(source_db.name + suffix)
                if side.exists():
                    _plain_copy(side, staged_db.with_name(
                        staged_db.name + suffix))

        # --- land: small files first, the database last -------------------
        if have_env:
            replace_with_retry(staging / ENV_NAME, target_env)
            report.files[ENV_NAME] = target_env.stat().st_size
        if session_copied:
            for staged in sorted(staging.glob("*.session*")):
                # the session (and its journal) land at the CONFIGURED
                # session path, not just the target dir
                dest = (target_session if staged.name.endswith(".session")
                        else target_session.with_name(staged.name))
                replace_with_retry(staged, dest)
                report.files[staged.name] = dest.stat().st_size
        _land_database(staged_db, target_db, replace_empty)
        shutil.rmtree(staging, ignore_errors=True)

    report.finished = _now()
    report.status = "ok"
    entry = report.as_dict()
    _append_report(target, entry)
    log.info("migrated archive: %s files from %s to %s",
             len(report.files), source, target)
    return entry


def _backup_target(target: Path, target_db: Path, target_session: Path,
                   env_file: Path, report: MigrationReport) -> Path:
    """Back up the files an import is about to replace (recoverable)."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = target / "backups" / f"{_REPLACE_BACKUP_PREFIX}{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for src in (target_db,
                target_db.with_name(target_db.name + "-wal"),
                target_db.with_name(target_db.name + "-shm"),
                target_session,
                target_session.with_name(target_session.name + "-journal")):
        if src.exists():
            shutil.copy2(src, backup_dir / src.name)
    if env_file.exists():
        shutil.copy2(env_file, backup_dir / ENV_NAME)
    return backup_dir


def _land_database(staged_db: Path, target_db: Path,
                  replace_empty: bool) -> None:
    """Put the staged snapshot where the app will read it.

    Target exists (the running app's empty archive): restore IN PLACE
    with SQLite's backup API. WAL mode lets this proceed while other
    connections are open - replacing the file instead would corrupt
    state (a stale -wal belongs to the old main db) and collides with
    Windows file locks.

    Target missing (fresh install auto-migration): atomically move the
    staged file in; leftover -wal/-shm from a crashed run can exist only
    without a live database, so removing them is lock-free.
    """
    if target_db.exists():
        dst = sqlite3.connect(target_db, timeout=20.0)
        try:
            src = sqlite3.connect(staged_db)
            try:
                src.backup(dst)
                dst.commit()
            finally:
                src.close()
        finally:
            dst.close()
        return
    for suffix in ("-wal", "-shm"):
        side = target_db.with_name(target_db.name + suffix)
        if side.exists():
            side.unlink(missing_ok=True)
    replace_with_retry(staged_db, target_db)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def replace_with_retry(src: Path, dst: Path, attempts: int = 6,
                       delay: float = 0.5) -> None:
    """os.replace with a short retry. On Windows a just-closed SQLite
    connection can hold the target for a few hundred milliseconds; an
    in-flight API request may still have it open. Honest PermissionError
    after the retries - never a silent partial state."""
    last: OSError | None = None
    for _i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError as e:
            last = e
            time.sleep(delay)
    raise MigrationError(
        f"Could not replace {dst.name} - it may be in use. Close other "
        f"application views and try again. ({last})")


def unlink_with_retry(path: Path, attempts: int = 6,
                      delay: float = 0.5) -> None:
    """Best-effort delete with the same short-retry contract."""
    last: OSError | None = None
    for _i in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError as e:
            last = e
            time.sleep(delay)
    raise MigrationError(
        f"Could not delete {path.name} - it may be in use. "
        f"Close other application views and try again. ({last})")


# ---------------------------------------------------------------------------
# Startup auto-migration (packaged apps)
# ---------------------------------------------------------------------------

def auto_migrate() -> dict | None:
    """Detect a legacy archive next to the installed executable and copy it
    into the canonical user-data directory. Frozen builds only; a no-op
    everywhere else, and never when explicit path overrides are set (the
    user has already told us where their data lives).
    """
    if not config.IS_FROZEN:
        return None
    if (os.environ.get("TG_DATA_DIR")
            or os.environ.get("TG_DB_PATH")
            or os.environ.get("TG_SESSION_PATH")):
        return None
    target = config.DATA_DIR
    if (target / DB_NAME).exists():
        return None                      # fresh or already migrated
    for candidate in (config.INSTALL_DIR / "data", config.INSTALL_DIR):
        if (candidate / DB_NAME).exists():
            log.info("found a legacy archive at %s - migrating to %s",
                     candidate, target)
            return migrate_data(candidate, target)
    return None
