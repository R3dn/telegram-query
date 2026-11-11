"""General endpoints: health (liveness), readiness, and first-run
application state."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

import auth
import config
import db
import desktop

from . import open_db

router = APIRouter()


@router.get("/api/health")
def health():
    """Liveness: the process is up. Deliberately touches nothing - a
    liveness probe must not fail because a dependency is slow."""
    return {"ok": True, "version": config.__version__}


@router.get("/api/health/ready")
def readiness():
    """Readiness: can this instance serve requests? Fails only when the
    archive database is unreachable (the one hard dependency). Optional
    dependencies (Telegram session, AI provider) are reported as
    informational and can never fail readiness by design."""
    checks = {"db": False}
    try:
        with open_db() as conn:
            conn.execute("SELECT 1 FROM app_settings LIMIT 1").fetchone()
        checks["db"] = True
    except Exception:  # noqa: BLE001 - reported, not raised
        return JSONResponse(
            {"ok": False, "checks": checks,
             "error": "archive database unavailable"},
            status_code=503)
    return {
        "ok": True,
        "checks": checks,
        "telegram_configured": config.settings.telegram_configured,
        "ai_configured": config.settings.ai_configured,
        "version": config.__version__,
    }


@router.post("/api/app/quit")
def quit_app():
    """Explicit Exit (desktop mode). The packaged app's UI sends this;
    the desktop runtime stops Uvicorn, which runs the FastAPI lifespan's
    graceful shutdown (running jobs cancel at their next checkpoint).
    In a source run there is no desktop runtime to stop - reported
    honestly instead of pretending to quit.
    """
    if not desktop.request_quit():
        return JSONResponse(
            {"ok": False,
             "error": "No desktop runtime in this process "
                      "(source run) - stop the dev server with Ctrl+C."},
            status_code=409)
    return {"ok": True}


@router.get("/api/app/state")
def app_state():
    """Everything the UI needs to pick the right screen: wizard, empty
    states, or the archive. Contains no secrets."""
    with open_db() as conn:
        s = db.stats(conn)
    return {
        "version": config.__version__,
        "desktop_mode": desktop.is_desktop(),
        "telegram_configured": config.settings.telegram_configured,
        "authenticated": auth.AUTH_STATE["authenticated"],
        "auth_user": auth.AUTH_STATE["user"],
        "tracked_groups": s["chats"],
        "messages": s["messages"],
        "pending_backfills": s["pending_backfills"],
        "last_message": s["last_message"],
        "ai_configured": config.settings.ai_configured,
        "ai_provider_host": config.settings.ai_provider_host,
        "ai_model": config.settings.ai_model,
    }
