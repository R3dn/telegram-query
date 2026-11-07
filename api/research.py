"""Research briefs API (v0.5): create/list/read/regenerate/delete briefs,
version history, deterministic staleness, and the generation job."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config
import jobs
import research

from . import open_db

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _brief_dict(conn, row, with_latest=True) -> dict:
    d = dict(row)
    d["chat_ids"] = json.loads(d.get("chat_ids") or "[]")
    if not with_latest:
        return d
    ver = research.latest_version(conn, d["id"])
    if ver:
        d["latest"] = {
            "version": ver["version"],
            "created_at": ver["created_at"],
            "model": ver["model"],
            "prompt_version": ver["prompt_version"],
            "answer_md": ver["answer_md"],
            "citations": research.version_citations(conn, ver["id"]),
        }
        d["stale_count"] = research.staleness(conn, d["id"])
    else:
        d["latest"] = None
        d["stale_count"] = 0
    return d


class BriefRequest(BaseModel):
    question: str = Field(min_length=4, max_length=2000)
    chat_ids: list[int] = Field(default_factory=list)
    date_from: str | None = Field(default=None, max_length=10)
    date_to: str | None = Field(default=None, max_length=10)


@router.get("/api/briefs")
def list_briefs():
    with open_db() as conn:
        rows = conn.execute(
            "SELECT * FROM briefs ORDER BY updated_at DESC").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["chat_ids"] = json.loads(d.get("chat_ids") or "[]")
            ver = research.latest_version(conn, d["id"])
            d["latest_version"] = ver["version"] if ver else None
            d["latest_at"] = ver["created_at"] if ver else None
            d["stale_count"] = research.staleness(conn, d["id"])
            out.append(d)
        return out


@router.post("/api/briefs")
def create_brief(req: BriefRequest):
    """Persist the brief first (restart-safe), then queue generation."""
    with open_db() as conn:
        brief_id = research.create_brief(
            conn, req.question, chat_ids=req.chat_ids,
            date_from=req.date_from, date_to=req.date_to)
    started = _queue_generate(brief_id)
    return {"id": brief_id, "queued": started}


@router.get("/api/briefs/{brief_id}")
def get_brief(brief_id: int):
    with open_db() as conn:
        row = research.get_brief(conn, brief_id)
        if not row:
            return JSONResponse({"error": "brief not found"}, status_code=404)
        return _brief_dict(conn, row)


@router.get("/api/briefs/{brief_id}/versions")
def get_versions(brief_id: int):
    with open_db() as conn:
        if not research.get_brief(conn, brief_id):
            return JSONResponse({"error": "brief not found"}, status_code=404)
        rows = conn.execute(
            "SELECT version, answer_md, model, prompt_version, created_at "
            "FROM brief_versions WHERE brief_id=? ORDER BY version DESC",
            (brief_id,)).fetchall()
        return [dict(r) for r in rows]


class BriefPatch(BaseModel):
    question: str | None = Field(default=None, min_length=4, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)
    chat_ids: list[int] | None = None
    date_from: str | None = None
    date_to: str | None = None


@router.patch("/api/briefs/{brief_id}")
def patch_brief(brief_id: int, req: BriefPatch):
    with open_db() as conn:
        if not research.get_brief(conn, brief_id):
            return JSONResponse({"error": "brief not found"}, status_code=404)
        sets, params = ["updated_at=?"], [_now()]
        if req.question is not None:
            sets.append("question=?")
            params.append(req.question.strip())
        if req.notes is not None:
            sets.append("notes=?")
            params.append(req.notes)
        if req.chat_ids is not None:
            sets.append("chat_ids=?")
            params.append(json.dumps(req.chat_ids))
        if req.date_from is not None:
            sets.append("date_from=?")
            params.append(req.date_from or None)
        if req.date_to is not None:
            sets.append("date_to=?")
            params.append(req.date_to or None)
        conn.execute(
            f"UPDATE briefs SET {', '.join(sets)} WHERE id=?",
            (*params, brief_id))
        conn.commit()
        return _brief_dict(conn, research.get_brief(conn, brief_id))


@router.post("/api/briefs/{brief_id}/regenerate")
def regenerate(brief_id: int):
    """Queue a fresh run - saved as a NEW version (history preserved)."""
    with open_db() as conn:
        if not research.get_brief(conn, brief_id):
            return JSONResponse({"error": "brief not found"}, status_code=404)
    started = _queue_generate(brief_id)
    return {"queued": started}


@router.delete("/api/briefs/{brief_id}")
def delete_brief(brief_id: int):
    with open_db() as conn:
        cur = conn.execute("DELETE FROM briefs WHERE id=?", (brief_id,))
        conn.commit()
        if cur.rowcount == 0:
            return JSONResponse({"error": "brief not found"}, status_code=404)
    return {"ok": True}


def _queue_generate(brief_id: int) -> bool:
    if not config.settings.ai_configured:
        return False
    return jobs.JOBS.start(
        "brief", lambda: jobs.run_brief_job(brief_id))
