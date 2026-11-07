"""Saved searches (v0.4): named search + filter sets, CRUD + run/duplicate.

A saved search stores the query and its filters - never the result rows.
Running one re-executes the search against the live archive.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api import open_db

router = APIRouter()

MAX_NAME = 100
MAX_QUERY = 1000
MAX_SAVED = 100   # keep the list manageable; delete to make room


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_to_dict(row) -> dict:
    d = dict(row)
    try:
        d["chat_ids"] = json.loads(d.get("chat_ids") or "[]")
    except ValueError:
        d["chat_ids"] = []
    return d


def _get(conn, sid: int):
    return conn.execute(
        "SELECT * FROM saved_searches WHERE id=?", (sid,)).fetchone()


class SavedSearchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_NAME)
    q: str = Field(default="", max_length=MAX_QUERY)
    chat_ids: list[int] = Field(default_factory=list)
    sender: str = Field(default="", max_length=200)
    media: str = Field(default="", max_length=1)   # '' | '0' | '1'
    date_from: str = Field(default="", max_length=10)
    date_to: str = Field(default="", max_length=10)
    sort: str = Field(default="desc", max_length=4)


@router.get("/api/saved-searches")
def list_saved():
    with open_db() as conn:
        rows = conn.execute(
            "SELECT * FROM saved_searches "
            "ORDER BY COALESCE(last_used_at, created_at) DESC").fetchall()
        return [_row_to_dict(r) for r in rows]


@router.post("/api/saved-searches")
def create_saved(req: SavedSearchRequest):
    with open_db() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM saved_searches").fetchone()["c"]
        if n >= MAX_SAVED:
            return JSONResponse(
                {"error": f"Too many saved searches (max {MAX_SAVED}) - "
                          "delete one first."},
                status_code=400)
        now = _now()
        cur = conn.execute(
            """INSERT INTO saved_searches
               (name, q, chat_ids, sender, media, date_from, date_to, sort,
                created_at, last_used_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (req.name.strip(), req.q.strip(),
             json.dumps([c for c in req.chat_ids if isinstance(c, int)]),
             req.sender.strip(), req.media, req.date_from.strip(),
             req.date_to.strip(), req.sort if req.sort in ("asc", "desc") else "desc",
             now, now),
        )
        conn.commit()
        return _row_to_dict(_get(conn, cur.lastrowid))


@router.patch("/api/saved-searches/{sid}")
def update_saved(sid: int, req: SavedSearchRequest):
    """Full replace of the stored definition (rename or edit)."""
    with open_db() as conn:
        if not _get(conn, sid):
            return JSONResponse({"error": "saved search not found"},
                                status_code=404)
        conn.execute(
            """UPDATE saved_searches SET
               name=?, q=?, chat_ids=?, sender=?, media=?, date_from=?,
               date_to=?, sort=? WHERE id=?""",
            (req.name.strip(), req.q.strip(),
             json.dumps([c for c in req.chat_ids if isinstance(c, int)]),
             req.sender.strip(), req.media, req.date_from.strip(),
             req.date_to.strip(),
             req.sort if req.sort in ("asc", "desc") else "desc", sid),
        )
        conn.commit()
        return _row_to_dict(_get(conn, sid))


@router.delete("/api/saved-searches/{sid}")
def delete_saved(sid: int):
    with open_db() as conn:
        cur = conn.execute("DELETE FROM saved_searches WHERE id=?", (sid,))
        conn.commit()
        if cur.rowcount == 0:
            return JSONResponse({"error": "saved search not found"},
                                status_code=404)
        return {"ok": True}


@router.post("/api/saved-searches/{sid}/duplicate")
def duplicate_saved(sid: int):
    with open_db() as conn:
        row = _get(conn, sid)
        if not row:
            return JSONResponse({"error": "saved search not found"},
                                status_code=404)
        now = _now()
        name = row["name"][: MAX_NAME - 7] + " (copy)"
        cur = conn.execute(
            """INSERT INTO saved_searches
               (name, q, chat_ids, sender, media, date_from, date_to, sort,
                created_at, last_used_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (name, row["q"], row["chat_ids"], row["sender"], row["media"],
             row["date_from"], row["date_to"], row["sort"], now, now),
        )
        conn.commit()
        return _row_to_dict(_get(conn, cur.lastrowid))


@router.post("/api/saved-searches/{sid}/run")
def run_saved(sid: int):
    """Mark used (the client applies the definition to its live filters)."""
    with open_db() as conn:
        row = _get(conn, sid)
        if not row:
            return JSONResponse({"error": "saved search not found"},
                                status_code=404)
        conn.execute("UPDATE saved_searches SET last_used_at=? WHERE id=?",
                     (_now(), sid))
        conn.commit()
        return _row_to_dict(_get(conn, sid))
