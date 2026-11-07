"""Background job endpoints: start sync, poll status, stop/cancel."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import config
import jobs

router = APIRouter()


class StopRequest(BaseModel):
    clear_queue: bool = False


def _creds_error():
    return JSONResponse(
        {"error": "Telegram credentials not configured - set TG_API_ID and "
                  "TG_API_HASH in your .env file."},
        status_code=400)


@router.post("/api/sync")
def sync(days: int = None):
    if not config.settings.telegram_configured:
        return _creds_error()
    days = days if days is not None else config.settings.sync_days
    with jobs.JOBS.lock:
        queued_behind = ([jobs.JOBS.name] if jobs.JOBS.running else []) + \
                        [n for n, _ in jobs.JOBS.queue]
    started = jobs.JOBS.start("sync", lambda: jobs.run_sync_job(days=days))
    if not started:
        return {"started": False, "reason": "already_queued"}
    return {"started": True, "queued_behind": queued_behind}


@router.get("/api/job/status")
def job_status():
    with jobs.JOBS.lock:
        return {"running": jobs.JOBS.running, "name": jobs.JOBS.name,
                "log": jobs.JOBS.log,
                "queued": [n for n, _ in jobs.JOBS.queue],
                "last_done": jobs.JOBS.last_done}


@router.post("/api/job/stop")
def job_stop(req: StopRequest = None):
    """Ask the running job to stop at its next checkpoint.
    clear_queue=True also drops every queued (not yet started) job."""
    dropped = []
    with jobs.JOBS.lock:
        if req and req.clear_queue:
            while jobs.JOBS.queue:
                dropped.append(jobs.JOBS.queue.popleft()[0])
    stopping = False
    if jobs.JOBS.running:
        from sync import CANCEL
        CANCEL.set()
        stopping = True
    return {"stopping": stopping, "cleared": dropped}
