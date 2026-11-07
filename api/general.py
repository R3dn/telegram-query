"""General endpoints: health and first-run application state."""
from __future__ import annotations

from fastapi import APIRouter

import auth
import config
import db

from . import open_db

router = APIRouter()


@router.get("/api/health")
def health():
    return {"ok": True, "version": config.__version__}


@router.get("/api/app/state")
def app_state():
    """Everything the UI needs to pick the right screen: wizard, empty
    states, or the archive. Contains no secrets."""
    with open_db() as conn:
        s = db.stats(conn)
    return {
        "version": config.__version__,
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
