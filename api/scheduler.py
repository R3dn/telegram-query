"""Auto-sync scheduler endpoints (v0.4): view and configure the schedule."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import jobs
import scheduler
from api import open_db

router = APIRouter()


class SchedulerRequest(BaseModel):
    enabled: bool | None = None
    interval_min: int | None = None


@router.get("/api/scheduler")
def scheduler_state():
    with open_db() as conn:
        st = scheduler.get_state(conn)
    return st


@router.post("/api/scheduler")
def scheduler_config(req: SchedulerRequest):
    with open_db() as conn:
        try:
            st = scheduler.apply_config(conn, enabled=req.enabled,
                                        interval_min=req.interval_min)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
    return st


@router.post("/api/reindex")
def reindex_now():
    """Queue the text normalization reindex as a visible background job."""
    started = jobs.JOBS.start("reindex", jobs.run_reindex_job, front=True)
    return {"started": started, "reason": None if started else "already_queued"}
