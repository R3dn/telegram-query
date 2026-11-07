"""Monitor API (v0.6): watchlists CRUD + alerts inbox + check-now."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import db
import watchlists

from . import open_db, parse_groups

router = APIRouter()


def _row_dict(r) -> dict:
    d = dict(r)
    d["terms"] = json.loads(d.get("terms") or "[]")
    d["exclude_terms"] = json.loads(d.get("exclude_terms") or "[]")
    d["chat_ids"] = json.loads(d.get("chat_ids") or "[]")
    d["enabled"] = bool(d.get("enabled"))
    return d


class WatchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    terms: list[str] = Field(min_length=1, max_length=50)
    exclude_terms: list[str] = Field(default_factory=list, max_length=50)
    chat_ids: list[int] = Field(default_factory=list)
    enabled: bool = True


@router.get("/api/watchlists")
def list_watchlists():
    with open_db() as conn:
        rows = conn.execute(
            "SELECT * FROM watchlists ORDER BY created_at DESC").fetchall()
        counts = {r["watchlist_id"]: r["c"] for r in conn.execute(
            "SELECT watchlist_id, COUNT(*) c FROM alerts "
            "WHERE read=0 AND archived=0 GROUP BY watchlist_id").fetchall()}
        out = [_row_dict(r) for r in rows]
        for o in out:
            o["unread"] = counts.get(o["id"], 0)
        return out


@router.post("/api/watchlists")
def create_watch(req: WatchRequest):
    terms = [t.strip() for t in req.terms if t.strip()]
    if not terms:
        return JSONResponse({"error": "at least one search term is required"},
                            status_code=400)
    with open_db() as conn:
        cur = conn.execute(
            """INSERT INTO watchlists (name, terms, exclude_terms, chat_ids,
                 enabled, created_at) VALUES (?,?,?,?,?,?)""",
            (req.name.strip(),
             json.dumps(terms, ensure_ascii=False),
             json.dumps([t.strip() for t in req.exclude_terms if t.strip()],
                        ensure_ascii=False),
             json.dumps([c for c in req.chat_ids if isinstance(c, int)]),
             1 if req.enabled else 0,
             datetime.now(timezone.utc).replace(microsecond=0).isoformat()))
        conn.commit()
        return _row_dict(conn.execute("SELECT * FROM watchlists WHERE id=?",
                                      (cur.lastrowid,)).fetchone())


@router.patch("/api/watchlists/{wid}")
def patch_watch(wid: int, req: WatchRequest):
    with open_db() as conn:
        if not conn.execute("SELECT 1 FROM watchlists WHERE id=?",
                            (wid,)).fetchone():
            return JSONResponse({"error": "watchlist not found"},
                                status_code=404)
        conn.execute(
            """UPDATE watchlists SET name=?, terms=?, exclude_terms=?,
                 chat_ids=?, enabled=? WHERE id=?""",
            (req.name.strip(),
             json.dumps([t.strip() for t in req.terms if t.strip()],
                        ensure_ascii=False),
             json.dumps([t.strip() for t in req.exclude_terms if t.strip()],
                        ensure_ascii=False),
             json.dumps([c for c in req.chat_ids if isinstance(c, int)]),
             1 if req.enabled else 0, wid))
        conn.commit()
        return _row_dict(conn.execute("SELECT * FROM watchlists WHERE id=?",
                                      (wid,)).fetchone())


@router.delete("/api/watchlists/{wid}")
def delete_watch(wid: int):
    with open_db() as conn:
        cur = conn.execute("DELETE FROM watchlists WHERE id=?", (wid,))
        conn.commit()
        if cur.rowcount == 0:
            return JSONResponse({"error": "watchlist not found"},
                                status_code=404)
    return {"ok": True}


class CheckRequest(BaseModel):
    backfill_days: int = Field(default=0, ge=0, le=90)


@router.post("/api/watchlists/check")
def check_now(req: CheckRequest = None):
    """Evaluate new messages right now (and optionally rewind the
    watermark to cover recent days - useful for new watchlists)."""
    with open_db() as conn:
        if req and req.backfill_days > 0:
            since = (datetime.now(timezone.utc)
                     - timedelta(days=req.backfill_days)).strftime("%Y-%m-%d")
            for r in conn.execute(
                    "SELECT chat_id, MAX(msg_id) m FROM messages "
                    "WHERE date < ? GROUP BY chat_id", (since + "T23:59:59",)
                    ).fetchall():
                conn.execute(
                    "INSERT INTO watch_watermarks (chat_id, last_msg_id) "
                    "VALUES (?,?) ON CONFLICT(chat_id) DO UPDATE SET "
                    "last_msg_id=MIN(last_msg_id, excluded.last_msg_id)",
                    (r["chat_id"], r["m"]))
            conn.commit()
        stats = watchlists.evaluate_new(conn)
        unread = watchlists.unread_count(conn)
    return {"ok": True, **stats, "unread": unread}


@router.get("/api/alerts")
def list_alerts(state: str = "new", watchlist: int = None,
                group: str = "", limit: int = 200):
    """state: new | read | archived | all."""
    chat_filter = parse_groups(group)
    where, params = ["1=1"], []
    if state == "new":
        where.append("a.read=0 AND a.archived=0")
    elif state == "read":
        where.append("a.read=1 AND a.archived=0")
    elif state == "archived":
        where.append("a.archived=1")
    if watchlist:
        where.append("a.watchlist_id=?")
        params.append(watchlist)
    if chat_filter:
        marks = ",".join("?" * len(chat_filter))
        where.append(f"a.chat_id IN ({marks})")
        params.extend(chat_filter)
    with open_db() as conn:
        rows = conn.execute(
            f"""SELECT a.id, a.watchlist_id, a.chat_id, a.msg_id,
                       a.matched_term, a.created_at, a.read, a.archived,
                       m.text, m.date, m.sender_name, m.reply_to,
                       c.title AS chat_title, c.username AS chat_username,
                       w.name AS watchlist_name
                FROM alerts a
                JOIN messages m ON m.chat_id = a.chat_id AND m.msg_id = a.msg_id
                JOIN chats c   ON c.chat_id = m.chat_id
                JOIN watchlists w ON w.id = a.watchlist_id
                WHERE {' AND '.join(where)}
                ORDER BY m.date DESC LIMIT ?""",
            (*params, min(limit, 500))).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["tg_link"] = db.message_link(d["chat_id"],
                                            d.pop("chat_username"),
                                            d["msg_id"])
            out.append(d)
        return out


class AlertAction(BaseModel):
    action: str = Field(max_length=16)   # read | unread | archive | unarchive


@router.post("/api/alerts/{aid}")
def alert_action(aid: int, req: AlertAction):
    with open_db() as conn:
        if not conn.execute("SELECT 1 FROM alerts WHERE id=?",
                            (aid,)).fetchone():
            return JSONResponse({"error": "alert not found"}, status_code=404)
        mapping = {
            "read": "read=1", "unread": "read=0",
            "archive": "archived=1, read=1", "unarchive": "archived=0",
        }
        if req.action not in mapping:
            return JSONResponse({"error": "unknown action"}, status_code=400)
        conn.execute(f"UPDATE alerts SET {mapping[req.action]} WHERE id=?",
                     (aid,))
        conn.commit()
        with open_db() as c2:
            unread = watchlists.unread_count(c2)
    return {"ok": True, "unread": unread}


@router.delete("/api/alerts/{aid}")
def delete_alert(aid: int):
    with open_db() as conn:
        cur = conn.execute("DELETE FROM alerts WHERE id=?", (aid,))
        conn.commit()
        if cur.rowcount == 0:
            return JSONResponse({"error": "alert not found"}, status_code=404)
    return {"ok": True}


@router.get("/api/alerts/unread")
def alerts_unread():
    with open_db() as conn:
        return {"unread": watchlists.unread_count(conn)}
