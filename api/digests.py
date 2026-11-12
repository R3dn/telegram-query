"""Digests API (v0.6): schedules, history, on-demand generation, export."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config
import db
import jobs

from . import open_db

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sched_dict(r) -> dict:
    d = dict(r)
    d["chat_ids"] = json.loads(d.get("chat_ids") or "[]")
    d["enabled"] = bool(d.get("enabled"))
    return d


def _digest_dict(conn, r) -> dict:
    d = dict(r)
    d["citations"] = []
    cites = conn.execute(
        """SELECT dc.idx, dc.chat_id, dc.msg_id, dc.excerpt, m.text, m.date,
                  m.sender_name, c.title AS chat_title, c.username AS chat_username
           FROM digest_citations dc
           LEFT JOIN messages m ON m.chat_id = dc.chat_id AND m.msg_id = dc.msg_id
           LEFT JOIN chats c   ON c.chat_id = m.chat_id
           WHERE dc.digest_id=? ORDER BY dc.idx""", (d["id"],)).fetchall()
    for c in cites:
        cd = dict(c)
        cd["tg_link"] = db.message_link(cd["chat_id"],
                                       cd.pop("chat_username"), cd["msg_id"])
        cd["missing"] = cd.get("text") is None
        d["citations"].append(cd)
    return d


class ScheduleRequest(BaseModel):
    frequency: str = Field(default="daily", max_length=10)   # daily|weekly
    chat_ids: list[int] = Field(default_factory=list)
    hour: int = Field(default=9, ge=0, le=23)
    weekday: int = Field(default=6, ge=0, le=6)
    language: str = Field(default="auto", max_length=4)     # auto|en|ar
    enabled: bool = True


@router.get("/api/digests/schedules")
def list_schedules():
    with open_db() as conn:
        rows = conn.execute(
            "SELECT * FROM digest_schedules ORDER BY created_at").fetchall()
        return [_sched_dict(r) for r in rows]


@router.post("/api/digests/schedules")
def create_schedule(req: ScheduleRequest):
    if req.frequency not in ("daily", "weekly"):
        return JSONResponse({"error": "frequency must be daily|weekly"},
                            status_code=400)
    with open_db() as conn:
        cur = conn.execute(
            """INSERT INTO digest_schedules (frequency, chat_ids, hour,
                 weekday, language, enabled, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (req.frequency, json.dumps(req.chat_ids), req.hour, req.weekday,
             req.language, 1 if req.enabled else 0, _now()))
        conn.commit()
        return _sched_dict(conn.execute(
            "SELECT * FROM digest_schedules WHERE id=?",
            (cur.lastrowid,)).fetchone())


@router.patch("/api/digests/schedules/{sid}")
def patch_schedule(sid: int, req: ScheduleRequest):
    with open_db() as conn:
        if not conn.execute("SELECT 1 FROM digest_schedules WHERE id=?",
                            (sid,)).fetchone():
            return JSONResponse({"error": "schedule not found"}, status_code=404)
        conn.execute(
            """UPDATE digest_schedules SET frequency=?, chat_ids=?, hour=?,
                 weekday=?, language=?, enabled=? WHERE id=?""",
            (req.frequency, json.dumps(req.chat_ids), req.hour, req.weekday,
             req.language, 1 if req.enabled else 0, sid))
        conn.commit()
        return _sched_dict(conn.execute(
            "SELECT * FROM digest_schedules WHERE id=?", (sid,)).fetchone())


@router.delete("/api/digests/schedules/{sid}")
def delete_schedule(sid: int):
    with open_db() as conn:
        cur = conn.execute("DELETE FROM digest_schedules WHERE id=?", (sid,))
        conn.commit()
        if cur.rowcount == 0:
            return JSONResponse({"error": "schedule not found"}, status_code=404)
    return {"ok": True}


@router.get("/api/digests")
def list_digests(schedule: int = None, limit: int = 100):
    where, params = ["1=1"], []
    if schedule:
        where.append("schedule_id=?")
        params.append(schedule)
    with open_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM digests WHERE {' AND '.join(where)} "
            "ORDER BY created_at DESC LIMIT ?",
            (*params, max(1, min(limit, 200)))).fetchall()
        # list view: content preview only (full body on the detail endpoint)
        return [{**{k: v for k, v in dict(r).items()},
                 "content_md": dict(r)["content_md"][:220] + "…"}
                for r in rows]


@router.get("/api/digests/{did}")
def get_digest(did: int):
    with open_db() as conn:
        r = conn.execute("SELECT * FROM digests WHERE id=?", (did,)).fetchone()
        if not r:
            return JSONResponse({"error": "digest not found"}, status_code=404)
        return _digest_dict(conn, r)


@router.delete("/api/digests/{did}")
def delete_digest(did: int):
    with open_db() as conn:
        cur = conn.execute("DELETE FROM digests WHERE id=?", (did,))
        conn.commit()
        if cur.rowcount == 0:
            return JSONResponse({"error": "digest not found"}, status_code=404)
    return {"ok": True}


class GenerateRequest(BaseModel):
    chat_ids: list[int] = Field(default_factory=list)
    period_start: str | None = Field(default=None, max_length=19)
    period_end: str | None = Field(default=None, max_length=19)
    frequency: str = Field(default="daily", max_length=10)
    language: str = Field(default="auto", max_length=4)


@router.post("/api/digests/generate")
def generate_now(req: GenerateRequest):
    """On-demand digest for a period, as a visible background job."""
    if not config.settings.ai_configured:
        return JSONResponse(
            {"error": "AI is not configured - set AI_API_KEY in Settings."},
            status_code=400)
    started = jobs.JOBS.start(
        "digest",
        lambda: jobs.run_digest_job(chat_ids=req.chat_ids or None,
                                    period_start=req.period_start,
                                    period_end=req.period_end,
                                    frequency=req.frequency,
                                    language=req.language))
    return {"started": started, "reason": None if started else "already_queued"}
