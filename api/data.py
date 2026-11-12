"""Data management endpoints for the desktop app.

Three small, deliberate operations on the user's archive:

* ``GET  /api/data/status``  - where the data lives, sizes, migration
  history. Powers the Settings "Data" section.
* ``POST /api/data/import``  - point a fresh install at an existing
  archive folder (source checkout or backup). Copy-based, backed up,
  idempotent, only into an empty archive (see :mod:`migration`).
* ``POST /api/data/erase``   - the explicit "remove everything" action.
  Deletes database, Telegram session, configuration and backups. The
  *uninstaller* deliberately never does this.

Loopback-only like the rest of the API (host guard); destructive actions
require an explicit confirmation token from the UI.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import config
import db
import desktop
import jobs
import migration

router = APIRouter()


class ImportRequest(BaseModel):
    source_dir: str


class EraseRequest(BaseModel):
    confirm: str


def _report_error(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


@router.get("/api/data/status")
def data_status():
    """Location and size of the user's data. Contains no secrets."""
    data_dir = Path(config.settings.data_dir)
    db_path = Path(config.settings.db_path)
    session = config.session_file(Path(config.settings.session_path))
    db_size = db_path.stat().st_size if db_path.exists() else 0
    try:
        history = json.loads(
            (data_dir / "migration-report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        history = []
    return {
        "desktop_mode": desktop.is_desktop(),
        "data_dir": str(data_dir),
        "db_path": str(db_path),
        "db_size": db_size,
        "session_exists": session.exists(),
        "session_path": str(session),
        "log_file": desktop.LOG_FILE or str(data_dir / "logs" / "app.log"),
        "migrations": history,
    }


@router.post("/api/data/import")
def import_data(req: ImportRequest):
    """Copy an existing archive (db + Telegram session + ``.env``) from
    ``source_dir`` into the application data directory. Only possible
    into an empty archive; the replaced files are backed up first."""
    source = Path(req.source_dir).expanduser()
    if not source.is_dir():
        return _report_error(f"No such folder: {source}")
    if not (source / migration.DB_NAME).exists():
        return _report_error(
            f"No {migration.DB_NAME} found in {source}. Pick the folder "
            "that contains your previous archive.")
    with jobs.JOBS.lock:
        if jobs.JOBS.running:
            return _report_error(
                "A background job is using the archive - stop it and try "
                "again.", status=409)
    # Operate on the archive the app is ACTUALLY using (honors
    # TG_DB_PATH / TG_SESSION_PATH overrides) - never on a directory the
    # configured database does not live in. A split layout (db and session
    # in different custom folders) is honestly unsupported.
    db_dir = Path(config.settings.db_path).parent
    session = config.session_file(Path(config.settings.session_path))
    if session.parent != db_dir:
        return _report_error(
            "Your database and Telegram session use separate custom "
            "locations (TG_DB_PATH / TG_SESSION_PATH). Import and erase "
            "manage the default single-folder layout - unset the "
            "overrides or move the files manually.")
    try:
        entry = migration.migrate_data(
            source, db_dir, replace_empty=True,
            target_db=Path(config.settings.db_path),
            target_session=session,
            env_target=config.ENV_FILE)
    except migration.MigrationError as e:
        return _report_error(str(e), status=409)
    except Exception as e:  # noqa: BLE001 - reported, never silent
        return _report_error(
            f"Import failed: {e}. Nothing in the source folder was "
            "modified.", status=500)
    # Pick up imported credentials/settings and refresh cached state.
    config.reload_settings()
    jobs.DIALOGS_CACHE.clear()
    import auth as tg_auth  # noqa: PLC0415 - late import, app already up
    tg_auth.AUTH_STATE.update(authenticated=None, user=None)
    tg_auth.run(tg_auth.refresh_auth_state())
    return {"ok": True, "migration": entry}


@router.post("/api/data/erase")
def erase_data(req: EraseRequest):
    """Explicitly remove ALL application data for this user: database,
    Telegram session, configuration, backups. Irreversible. The
    uninstaller never does this - it is only ever this deliberate action
    with a typed confirmation.
    """
    if req.confirm != "ERASE":
        return _report_error(
            'Type "ERASE" to confirm - this deletes your entire archive.',
            status=400)
    with jobs.JOBS.lock:
        if jobs.JOBS.running:
            return _report_error(
                "A background job is using the archive - stop it and try "
                "again.", status=409)
    data_dir = Path(config.settings.data_dir)
    db_path = Path(config.settings.db_path)
    session = config.session_file(Path(config.settings.session_path))
    deleted: list[str] = []
    try:
        # Explicit targets only - never a blanket directory delete, so a
        # custom TG_DATA_DIR location can never lose unrelated files.
        for p in (db_path,
                  db_path.with_name(db_path.name + "-wal"),
                  db_path.with_name(db_path.name + "-shm"),
                  session,
                  session.with_name(session.name + "-journal")):
            if p.exists():
                migration.unlink_with_retry(p)
                deleted.append(p.name)
        for name in (config.ENV_FILE,
                     data_dir / "migration-report.json",
                     data_dir / "runtime.json"):
            path = Path(name)
            if path.exists():
                migration.unlink_with_retry(path)
                deleted.append(path.name)
        for sub in ("backups",):
            d = data_dir / sub
            if d.is_dir():
                shutil.rmtree(d)
                deleted.append(sub + "/")
    except migration.MigrationError as e:
        return _report_error(str(e), status=409)
    # The UI reloads itself right after a successful erase; the SAME
    # process must then serve a fresh, schema-complete empty archive.
    # (a) db.get_db() runs its schema only once per path - without
    # dropping that guard the next connection would re-create an empty
    # file with no tables and every endpoint would 500 until restart.
    db.forget_initialized(str(db_path))
    # (b) "erase configuration" must be true for THIS process too: the
    # wizard persists credentials via config.update_env, which also
    # sets them in os.environ - drop them and rebuild settings so the
    # app honestly reports itself as unconfigured (the wizard reopens).
    for key in ("TG_API_ID", "TG_API_HASH", "TELEGRAM_API_ID",
                "TELEGRAM_API_HASH", "AI_API_KEY", "AI_BASE_URL",
                "AI_MODEL", "AI_MODEL_EXTRACT", "AI_MODEL_SYNTH",
                "AI_MODEL_EMBED"):
        os.environ.pop(key, None)
    config.reload_settings()
    # Reset cached in-process state; the archive starts over on next boot.
    jobs.DIALOGS_CACHE.clear()
    import auth as tg_auth  # noqa: PLC0415
    tg_auth.AUTH_STATE.update(authenticated=False, user=None)
    return {"ok": True, "deleted": deleted,
            "quit": desktop.is_desktop()}
