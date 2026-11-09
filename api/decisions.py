"""Decisions API (v0.8): list/filter/detail/confirm/correct/delete + the
extraction jobs and settings."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config
import db
import decisions
import jobs

from . import open_db, parse_groups

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_to_dict(conn, r) -> dict:
    d = dict(r)
    d["derived_status"] = decisions.derived_status(d)
    d["confidence_label"] = decisions.confidence_label(d.get("confidence"))
    d["human_added"] = d.get("prompt_version") == "manual"
    src = conn.execute(
        """SELECT s.chat_id, s.msg_id, m.text, m.date, m.sender_name,
                  c.title AS chat_title, c.username AS chat_username
           FROM decision_sources s
           LEFT JOIN messages m ON m.chat_id = s.chat_id AND m.msg_id = s.msg_id
           LEFT JOIN chats c   ON c.chat_id = m.chat_id
           WHERE s.decision_id=? ORDER BY m.date DESC""", (d["id"],)).fetchall()
    d["sources"] = []
    for s in src:
        sd = dict(s)
        sd["tg_link"] = db.message_link(sd["chat_id"],
                                        sd.pop("chat_username"), sd["msg_id"])
        sd["missing"] = sd.get("text") is None
        d["sources"].append(sd)
    return d


@router.get("/api/decisions")
def list_decisions(status: str = "", kind: str = "", owner: str = "",
                   group: str = "", q: str = "", from_: str = "",
                   to: str = "", sort: str = "recent", limit: int = 200):
    chat_filter = parse_groups(group)
    where = ["1=1"]
    params: list = []
    if status:
        # explicit status filter reaches everything, including dismissed
        where.append("(d.status=? OR d.user_status=?)")
        params.extend([status, status])
    else:
        # default view: human-dismissed decisions stay out of the way
        where.append("(d.user_status IS NULL OR d.user_status != 'dismissed')")
    if kind:
        where.append("d.kind=?")
        params.append(kind)
    if owner:
        where.append("LOWER(d.owner) LIKE ?")
        params.append(f"%{owner.lower()}%")
    if q:
        like = ("%" + q.replace("%", "\\%").replace("_", "\\_") + "%")
        where.append("(d.title LIKE ? ESCAPE '\\' OR d.detail LIKE ? ESCAPE '\\')")
        params.extend([like, like])
    if chat_filter:
        marks = ",".join("?" * len(chat_filter))
        where.append(
            f"d.id IN (SELECT decision_id FROM decision_sources "
            f"WHERE chat_id IN ({marks}))")
        params.extend(chat_filter)
    # last_seen window (when the decision was stated)
    if from_:
        where.append("d.last_seen >= ?")
        params.append(from_ + "T00:00:00")
    if to:
        where.append("d.last_seen <= ?")
        params.append(to + "T23:59:59")
    if sort == "due":
        order = "d.due_date IS NULL, d.due_date ASC, d.last_seen DESC"
    elif sort == "confidence":
        order = "d.confidence DESC NULLS LAST"
    else:
        order = "d.last_seen DESC"
    clauses = list(where)
    with open_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM decisions d WHERE {' AND '.join(clauses)} "
            f"ORDER BY {order} LIMIT ?",
            (*params, min(limit, 500))).fetchall()
        # status=overdue is derived, not stored: post-filter when asked
        out = [_row_to_dict(conn, r) for r in rows]
        if status == "overdue":
            out = [d for d in out if d["derived_status"] == "overdue"]
        return out


@router.get("/api/decisions/settings")
def decisions_settings():
    with open_db() as conn:
        auto = db.get_setting(conn, "decisions_auto", "0") == "1"
        watermark = json.loads(
            db.get_setting(conn, "decisions_watermark", "{}") or "{}")
        kinds = [r["kind"] for r in conn.execute(
            "SELECT DISTINCT kind FROM decisions WHERE kind IS NOT NULL "
            "ORDER BY kind").fetchall()]
        owners = [r["owner"] for r in conn.execute(
            "SELECT DISTINCT owner FROM decisions WHERE owner IS NOT NULL "
            "ORDER BY owner LIMIT 200").fetchall()]
    return {"auto": auto, "kinds": kinds, "owners": owners,
            "watermark": watermark}


@router.get("/api/decisions/{decision_id}")
def get_decision(decision_id: int):
    with open_db() as conn:
        r = conn.execute("SELECT * FROM decisions WHERE id=?",
                         (decision_id,)).fetchone()
        if not r:
            return JSONResponse({"error": "decision not found"}, status_code=404)
        return _row_to_dict(conn, r)


class DecisionPatch(BaseModel):
    user_status: str | None = Field(default=None, max_length=16)
    title: str | None = Field(default=None, max_length=300)
    detail: str | None = Field(default=None, max_length=2000)
    kind: str | None = Field(default=None, max_length=16)
    owner: str | None = Field(default=None, max_length=120)
    due_date: str | None = Field(default=None, max_length=10)
    status: str | None = Field(default=None, max_length=16)


@router.patch("/api/decisions/{decision_id}")
def patch_decision(decision_id: int, req: DecisionPatch):
    """Human verification: confirm / dismiss / correct fields."""
    if req.user_status is not None and \
            req.user_status not in ("confirmed", "dismissed", None):
        return JSONResponse(
            {"error": "user_status must be confirmed|dismissed"},
            status_code=400)
    if req.status is not None and \
            req.status not in ("proposed", "committed", "completed",
                               "cancelled", "unknown"):
        return JSONResponse(
            {"error": "status must be proposed|committed|completed|"
                      "cancelled|unknown"},
            status_code=400)
    if req.kind is not None and req.kind not in ("decision", "commitment",
                                                 "plan"):
        return JSONResponse(
            {"error": "kind must be decision|commitment|plan"},
            status_code=400)
    with open_db() as conn:
        if not conn.execute("SELECT 1 FROM decisions WHERE id=?",
                            (decision_id,)).fetchone():
            return JSONResponse({"error": "decision not found"}, status_code=404)
        sets, params = ["updated_at=?"], [_now()]
        for field in ("user_status", "title", "detail", "kind", "owner",
                      "due_date", "status"):
            v = getattr(req, field)
            if v is not None:
                sets.append(f"{field}=?")
                params.append(v.strip() if isinstance(v, str) else v)
        conn.execute(
            f"UPDATE decisions SET {', '.join(sets)} WHERE id=?",
            (*params, decision_id))
        conn.commit()
        r = conn.execute("SELECT * FROM decisions WHERE id=?",
                         (decision_id,)).fetchone()
        return _row_to_dict(conn, r)


@router.delete("/api/decisions/{decision_id}")
def delete_decision(decision_id: int):
    with open_db() as conn:
        cur = conn.execute("DELETE FROM decisions WHERE id=?", (decision_id,))
        conn.commit()
        if cur.rowcount == 0:
            return JSONResponse({"error": "decision not found"}, status_code=404)
    return {"ok": True}


class ManualDecision(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    detail: str = Field(default="", max_length=2000)
    kind: str | None = Field(default=None, max_length=16)
    owner: str | None = Field(default=None, max_length=120)
    due_date: str | None = Field(default=None, max_length=10)
    chat_id: int | None = None
    msg_id: int | None = None


@router.post("/api/decisions")
def add_manual(req: ManualDecision):
    """Manually add a decision: status committed, human-confirmed by design."""
    now = _now()
    key = decisions._identity_key(req.title, req.owner, req.due_date)
    with open_db() as conn:
        if req.chat_id is not None and req.msg_id is not None:
            if not conn.execute(
                    "SELECT 1 FROM messages WHERE chat_id=? AND msg_id=?",
                    (req.chat_id, req.msg_id)).fetchone():
                return JSONResponse(
                    {"error": "source message not found"}, status_code=404)
        cur = conn.execute(
            """INSERT INTO decisions (title, detail, kind, owner, due_date,
                 status, user_status, confidence, fingerprint,
                 prompt_version, model, first_seen, last_seen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (req.title.strip(), req.detail.strip(),
             req.kind if req.kind in ("decision", "commitment", "plan") else None,
             req.owner, req.due_date,
             "committed", "confirmed", 1.0, key + "|manual", "manual",
             "human", now, now, now))
        dec_id = cur.lastrowid
        if req.chat_id is not None and req.msg_id is not None:
            conn.execute(
                "INSERT OR IGNORE INTO decision_sources "
                "(decision_id, chat_id, msg_id) VALUES (?,?,?)",
                (dec_id, req.chat_id, req.msg_id))
        conn.commit()
        r = conn.execute("SELECT * FROM decisions WHERE id=?",
                         (dec_id,)).fetchone()
        return _row_to_dict(conn, r)


class ExtractRequest(BaseModel):
    chat_ids: list[int] = Field(default_factory=list)
    date_from: str | None = Field(default=None, max_length=10)
    date_to: str | None = Field(default=None, max_length=10)


@router.post("/api/decisions/extract")
def start_extract(req: ExtractRequest):
    """Queue the visible 'decisions' job over a scope (backfill)."""
    if not config.settings.ai_configured:
        return JSONResponse(
            {"error": "AI is not configured - set AI_API_KEY in Settings."},
            status_code=400)
    started = jobs.JOBS.start(
        "decisions",
        lambda: jobs.run_decisions_job(chat_ids=req.chat_ids or None,
                                       date_from=req.date_from,
                                       date_to=req.date_to))
    return {"started": started, "reason": None if started else "already_queued"}


class AutoRequest(BaseModel):
    enabled: bool


@router.post("/api/decisions/auto")
def set_auto(req: AutoRequest):
    """Toggle incremental extraction after each sync (post-sync hook)."""
    with open_db() as conn:
        db.set_setting(conn, "decisions_auto", "1" if req.enabled else "0")
        conn.commit()
        return {"auto": req.enabled}
