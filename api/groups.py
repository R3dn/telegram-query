"""Group management endpoints: track, untrack, dialog discovery."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import config
import db
import jobs

from . import open_db

router = APIRouter()


class TrackRequest(BaseModel):
    chat_ids: list[int]


class UntrackRequest(BaseModel):
    chat_ids: list[int]
    delete_messages: bool = False


def _creds_error():
    return JSONResponse(
        {"error": "Telegram credentials not configured - set TG_API_ID and "
                  "TG_API_HASH in your .env file."},
        status_code=400)


def _tracked_ids():
    with open_db() as conn:
        return {r["chat_id"] for r in
                conn.execute("SELECT chat_id FROM chats WHERE tracked=1").fetchall()}


@router.get("/api/dialogs")
def dialogs_get():
    """Cached list of the account's groups/channels with tracked flags."""
    if jobs.DIALOGS_CACHE["list"] is not None:
        tracked = _tracked_ids()
        return {"ready": True,
                "dialogs": [{**d, "tracked": d["chat_id"] in tracked}
                            for d in jobs.DIALOGS_CACHE["list"]]}
    return {"ready": False}


@router.post("/api/dialogs")
def dialogs_start():
    if not config.settings.telegram_configured:
        return _creds_error()
    # front=True: the listing is quick and unblocks the Manage UI
    started = jobs.JOBS.start("dialogs", jobs.fetch_dialogs_job, front=True)
    return {"started": started, "reason": None if started else "already_pending"}


@router.post("/api/groups/track")
def track(req: TrackRequest):
    if not req.chat_ids:
        return JSONResponse({"error": "chat_ids required"}, status_code=400)
    if not config.settings.telegram_configured:
        return _creds_error()
    tracked = _tracked_ids()
    new_ids = [cid for cid in req.chat_ids if cid not in tracked]
    if not new_ids:
        return {"started": False, "reason": "already_tracked"}
    with jobs.JOBS.lock:
        queued_behind = ([jobs.JOBS.name] if jobs.JOBS.running else []) + \
                        [n for n, _ in jobs.JOBS.queue]
    jobs.JOBS.start("track", lambda: jobs.run_sync_job(track=new_ids))
    return {"started": True, "chat_ids": new_ids, "queued_behind": queued_behind}


@router.post("/api/groups/untrack")
def untrack(req: UntrackRequest):
    """Untrack stops archiving a group. By default its messages are KEPT
    (hidden, reversible on re-track). delete_messages=true permanently
    removes them and resets the chat's sync state."""
    if not req.chat_ids:
        return JSONResponse({"error": "chat_ids required"}, status_code=400)
    with open_db() as conn:
        for cid in req.chat_ids:
            conn.execute("UPDATE chats SET tracked=0 WHERE chat_id=?", (cid,))
        if req.delete_messages:
            db.delete_chats_messages(conn, req.chat_ids)
        conn.commit()
    return {"ok": True, "deleted_messages": req.delete_messages}
