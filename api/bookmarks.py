"""Bookmarks + private notes (v0.4).

A bookmark references the ORIGINAL message (chat_id, msg_id) - it never
duplicates content, so it always reflects the archived original. Notes are
application metadata: they stay local and are never part of AI retrieval
context (the AI pipeline reads only `messages`).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import db
from api import open_db, parse_groups

router = APIRouter()

MAX_NOTE = 4000
MAX_QUERY = 200


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _decorate(rows: list[dict]) -> list[dict]:
    """Compute the open-in-Telegram link per row (never fabricated)."""
    for r in rows:
        r["tg_link"] = db.message_link(r["chat_id"], r.get("chat_username"),
                                       r["msg_id"])
    return rows


class BookmarkRequest(BaseModel):
    chat_id: int
    msg_id: int
    note: str = Field(default="", max_length=MAX_NOTE)


@router.get("/api/bookmarks")
def list_bookmarks(q: str = "", groups: str = "", limit: int = 500):
    """Bookmarked messages, newest first; `q` searches notes AND text."""
    q = (q or "").strip()
    if len(q) > MAX_QUERY:
        return JSONResponse({"error": "query too long"}, status_code=400)
    chat_filter = parse_groups(groups)
    with open_db() as conn:
        query = """
            SELECT b.note, b.created_at AS bookmarked_at,
                   b.updated_at AS note_updated_at,
                   m.chat_id, m.msg_id, m.date, m.sender_id, m.sender_name,
                   m.text, m.has_media, m.edited,
                   c.title AS chat_title, c.username AS chat_username
            FROM bookmarks b
            JOIN messages m ON m.chat_id = b.chat_id AND m.msg_id = b.msg_id
            JOIN chats c   ON c.chat_id = m.chat_id
            WHERE 1=1
        """
        params: list = []
        if q:
            like = ("%" + q.replace("\\", "\\\\").replace("%", "\\%")
                    .replace("_", "\\_") + "%")
            query += " AND (b.note LIKE ? ESCAPE '\\' OR m.text LIKE ? ESCAPE '\\')"
            params.extend([like, like])
        if chat_filter:
            marks = ",".join("?" * len(chat_filter))
            query += f" AND m.chat_id IN ({marks})"
            params.extend(chat_filter)
        query += (" ORDER BY m.date DESC, m.chat_id, m.msg_id"
                  f" LIMIT {max(1, min(limit, 1000))}")
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    return _decorate(rows)


@router.post("/api/bookmarks")
def upsert_bookmark(req: BookmarkRequest):
    """Create or update (star / un-star is a separate DELETE)."""
    now = _now()
    with open_db() as conn:
        exists = conn.execute(
            "SELECT 1 FROM messages WHERE chat_id=? AND msg_id=?",
            (req.chat_id, req.msg_id)).fetchone()
        if not exists:
            return JSONResponse(
                {"error": "message not found in the archive"},
                status_code=404)
        conn.execute(
            """INSERT INTO bookmarks (chat_id, msg_id, note, created_at, updated_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(chat_id, msg_id) DO UPDATE SET
                 note=excluded.note, updated_at=excluded.updated_at""",
            (req.chat_id, req.msg_id, req.note, now, now),
        )
        conn.commit()
    return {"ok": True, "chat_id": req.chat_id, "msg_id": req.msg_id,
            "note": req.note}


@router.delete("/api/bookmarks/{chat_id}/{msg_id}")
def delete_bookmark(chat_id: int, msg_id: int):
    with open_db() as conn:
        cur = conn.execute(
            "DELETE FROM bookmarks WHERE chat_id=? AND msg_id=?",
            (chat_id, msg_id))
        conn.commit()
        if cur.rowcount == 0:
            return JSONResponse({"error": "not bookmarked"}, status_code=404)
    return {"ok": True}
