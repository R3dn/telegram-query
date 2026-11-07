"""Archive endpoints: stats, groups, browsing, senders, search."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

import config
import db

from . import open_db, parse_groups

router = APIRouter()


def _decorate(rows: list[dict]) -> list[dict]:
    """Add the open-in-Telegram link to each row (None when none exists)."""
    for r in rows:
        r["tg_link"] = db.message_link(r["chat_id"], r.pop("chat_username", None),
                                       r["msg_id"])
    return rows


@router.get("/api/stats")
def stats():
    with open_db() as conn:
        s = db.stats(conn)
    s["ai_configured"] = config.settings.ai_configured
    return s


@router.get("/api/groups")
def groups():
    with open_db() as conn:
        rows = conn.execute("""
            SELECT c.chat_id, c.title, c.kind, c.username, c.last_synced,
                   COUNT(m.msg_id) AS message_count, MAX(m.date) AS last_message
            FROM chats c LEFT JOIN messages m ON m.chat_id = c.chat_id
            WHERE c.tracked = 1
            GROUP BY c.chat_id ORDER BY c.title COLLATE NOCASE
        """).fetchall()
        return [dict(r) for r in rows]


@router.get("/api/messages")
def messages(groups: str = "", sender: str = "", from_: str = "",
             to: str = "", media: int = None, cursor: str = "",
             limit: int = 50, sort: str = "desc", bookmarked: bool = None):
    with open_db() as conn:
        rows, next_cursor, has_more = db.browse(
            conn,
            chat_ids=parse_groups(groups) or None,
            sender=sender or None,
            date_from=from_ or None,
            date_to=to or None,
            media=media,
            cursor=cursor or None,
            limit=min(limit, 200),
            sort=sort,
            bookmarked=bookmarked,
        )
    return {"messages": _decorate(rows), "next_cursor": next_cursor,
            "has_more": has_more}


@router.get("/api/message/{chat_id}/{msg_id}")
def message_one(chat_id: int, msg_id: int):
    """Fetch one message by id (used by AI citations to open originals)."""
    with open_db() as conn:
        row = conn.execute(
            """SELECT m.chat_id, m.msg_id, m.date, m.sender_id, m.sender_name,
                      m.text, m.has_media, m.edited, c.title AS chat_title,
                      c.username AS chat_username,
                      (b.chat_id IS NOT NULL) AS bookmarked,
                      b.note AS bookmark_note
               FROM messages m JOIN chats c ON c.chat_id = m.chat_id
               LEFT JOIN bookmarks b
                      ON b.chat_id = m.chat_id AND b.msg_id = m.msg_id
               WHERE m.chat_id=? AND m.msg_id=?""",
            (chat_id, msg_id),
        ).fetchone()
        if row is None:
            return JSONResponse({"error": "message not found"}, status_code=404)
        return _decorate([dict(row)])[0]


@router.get("/api/senders")
def senders(groups: str = ""):
    with open_db() as conn:
        return db.senders(conn, chat_ids=parse_groups(groups) or None)


@router.get("/api/search")
def search(q: str = "", groups: str = "", sender: str = "",
           from_: str = "", to: str = "", limit: int = 200,
           bookmarked: bool = None):
    if not q.strip():
        return []
    if len(q) > 1000:
        return JSONResponse({"error": "Query too long (max 1000 characters)"},
                            status_code=400)
    with open_db() as conn:
        rows = db.search(
            conn,
            [p.strip() for p in q.split("|") if p.strip()],  # | = alternatives
            chat_ids=parse_groups(groups) or None,
            sender=sender or None,
            date_from=from_ or None,
            date_to=to or None,
            require_all=False,  # any-phrase match; ranking favors multi-hits
            limit=min(limit, 500),
            bookmarked=bookmarked,
        )
    return _decorate(rows)
