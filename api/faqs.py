"""FAQ API (v0.6): discovery job, review workflow, list/detail."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import db
import jobs

from . import open_db

router = APIRouter()

_VALID_STATUS = {"candidate", "approved", "rejected", "needs_review", "outdated"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_dict(conn, r) -> dict:
    d = dict(r)
    d["source_questions"] = json.loads(d.get("source_questions") or "[]")
    # enrich question sources with titles + links (inspectable, reversible)
    qs = []
    for s in d["source_questions"]:
        row = conn.execute(
            """SELECT m.text, m.date, c.title AS chat_title,
                      c.username AS chat_username
               FROM messages m JOIN chats c ON c.chat_id = m.chat_id
               WHERE m.chat_id=? AND m.msg_id=?""",
            (s.get("chat_id"), s.get("msg_id"))).fetchone()
        entry = dict(s)
        if row:
            entry["text"] = row["text"]
            entry["chat_title"] = row["chat_title"]
        else:
            entry["text"] = None
            entry["chat_title"] = None
        entry["tg_link"] = db.message_link(s.get("chat_id"),
                                           row["chat_username"] if row else None,
                                           s.get("msg_id"))
        qs.append(entry)
    d["source_questions"] = qs
    return d


@router.get("/api/faqs")
def list_faqs(status: str = "", q: str = "", limit: int = 200):
    where, params = ["1=1"], []
    if status:
        where.append("status=?")
        params.append(status)
    if q:
        like = "%" + q.replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(question LIKE ? ESCAPE '\\' OR answer_md LIKE ? ESCAPE '\\')")
        params.extend([like, like])
    with open_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM faq_clusters WHERE {' AND '.join(where)} "
            "ORDER BY frequency DESC, last_seen DESC LIMIT ?",
            (*params, max(1, min(limit, 500)))).fetchall()
        return [_row_dict(conn, r) for r in rows]


@router.get("/api/faqs/{fid}")
def get_faq(fid: int):
    with open_db() as conn:
        r = conn.execute("SELECT * FROM faq_clusters WHERE id=?",
                          (fid,)).fetchone()
        if not r:
            return JSONResponse({"error": "FAQ not found"}, status_code=404)
        return _row_dict(conn, r)


class FaqPatch(BaseModel):
    status: str | None = Field(default=None, max_length=16)
    question: str | None = Field(default=None, max_length=300)
    answer_md: str | None = Field(default=None, max_length=8000)


@router.patch("/api/faqs/{fid}")
def patch_faq(fid: int, req: FaqPatch):
    """Human review: approve / reject / outdated, or edit the record."""
    if req.status is not None and req.status not in _VALID_STATUS:
        return JSONResponse(
            {"error": "status must be one of " + ", ".join(sorted(_VALID_STATUS))},
            status_code=400)
    with open_db() as conn:
        if not conn.execute("SELECT 1 FROM faq_clusters WHERE id=?",
                            (fid,)).fetchone():
            return JSONResponse({"error": "FAQ not found"}, status_code=404)
        sets, params = ["updated_at=?"], [_now()]
        if req.status is not None:
            sets.append("status=?")
            params.append(req.status)
        if req.question is not None and req.question.strip():
            sets.append("question=?")
            params.append(req.question.strip())
        if req.answer_md is not None:
            sets.append("answer_md=?")
            params.append(req.answer_md)
        conn.execute(
            f"UPDATE faq_clusters SET {', '.join(sets)} WHERE id=?",
            (*params, fid))
        conn.commit()
        return _row_dict(conn, conn.execute(
            "SELECT * FROM faq_clusters WHERE id=?", (fid,)).fetchone())


@router.delete("/api/faqs/{fid}")
def delete_faq(fid: int):
    with open_db() as conn:
        cur = conn.execute("DELETE FROM faq_clusters WHERE id=?", (fid,))
        conn.commit()
        if cur.rowcount == 0:
            return JSONResponse({"error": "FAQ not found"}, status_code=404)
    return {"ok": True}


class DiscoverRequest(BaseModel):
    chat_ids: list[int] = Field(default_factory=list)
    days: int = Field(default=90, ge=1, le=365)


@router.post("/api/faqs/discover")
def start_discovery(req: DiscoverRequest):
    """Queue the FAQ discovery job over a scope."""
    started = jobs.JOBS.start(
        "faq",
        lambda: jobs.run_faq_job(chat_ids=req.chat_ids or None, days=req.days))
    return {"started": started, "reason": None if started else "already_queued"}
