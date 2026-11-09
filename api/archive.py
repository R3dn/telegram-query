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
        # v9: correlated subqueries instead of LEFT JOIN + GROUP BY over the
        # whole messages table (measured 150ms -> ~16ms at 500k rows).
        # COUNT(*) == COUNT(m.msg_id) here (msg_id is NOT NULL, PK) and
        # MAX(m.date) resolves through idx_messages_chat_date without a
        # single row load; empty chats read 0/NULL exactly as the JOIN did.
        rows = conn.execute("""
            SELECT c.chat_id, c.title, c.kind, c.username, c.last_synced,
                   (SELECT COUNT(*) FROM messages m
                     WHERE m.chat_id = c.chat_id) AS message_count,
                   (SELECT MAX(m.date) FROM messages m
                     WHERE m.chat_id = c.chat_id) AS last_message
            FROM chats c
            WHERE c.tracked = 1
            ORDER BY c.title COLLATE NOCASE
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
                      m.text, m.has_media, m.edited, m.reply_to,
                      c.title AS chat_title,
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


@router.get("/api/message/{chat_id}/{msg_id}/context")
def message_context(chat_id: int, msg_id: int, before: int = 12,
                    after: int = 12):
    """Conversation reconstruction around one message (v0.7): the reply
    chain where captured, direct replies, and the same-chat id window.
    Honest limits: reply_to is captured going forward (v0.5+); the
    window is Telegram's natural message order."""
    with open_db() as conn:
        ctx = db.conversation(conn, chat_id, msg_id,
                              before=min(before, 50), after=min(after, 50))
        if ctx is None:
            return JSONResponse({"error": "message not found"}, status_code=404)
        out = {"target": _decorate([ctx["target"]])[0],
               "ancestors": _decorate(ctx["ancestors"]),
               "replies": _decorate(ctx["replies"]),
               "rows": []}
        for r in ctx["rows"]:
            d = _decorate([r])[0]
            d["is_target"] = r.get("is_target", 0)
            d["is_reply"] = r.get("is_reply", 0)
            out["rows"].append(d)
        return out


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
