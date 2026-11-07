"""Deals API (v0.5): list/filter/detail/confirm/correct/delete + the
extraction jobs and settings."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config
import db
import deals
import jobs

from . import open_db, parse_groups

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_to_dict(conn, r) -> dict:
    d = dict(r)
    d["derived_status"] = deals.derived_status(d)
    d["confidence_label"] = deals.confidence_label(d.get("confidence"))
    d["human_added"] = d.get("prompt_version") == "manual"
    src = conn.execute(
        """SELECT s.chat_id, s.msg_id, m.text, m.date, m.sender_name,
                  c.title AS chat_title, c.username AS chat_username
           FROM deal_sources s
           LEFT JOIN messages m ON m.chat_id = s.chat_id AND m.msg_id = s.msg_id
           LEFT JOIN chats c   ON c.chat_id = m.chat_id
           WHERE s.deal_id=? ORDER BY m.date DESC""", (d["id"],)).fetchall()
    d["sources"] = []
    for s in src:
        sd = dict(s)
        sd["tg_link"] = db.message_link(sd["chat_id"],
                                        sd.pop("chat_username"), sd["msg_id"])
        sd["missing"] = sd.get("text") is None
        d["sources"].append(sd)
    return d


@router.get("/api/deals")
def list_deals(status: str = "", category: str = "", vendor: str = "",
               group: str = "", q: str = "", from_: str = "", to: str = "",
               sort: str = "recent", limit: int = 200):
    chat_filter = parse_groups(group)
    where = ["1=1"]
    params: list = []
    if status:
        # explicit status filter reaches everything, including dismissed
        where.append("(d.status=? OR d.user_status=?)")
        params.extend([status, status])
    else:
        # default view: human-dismissed deals stay out of the way
        where.append("(d.user_status IS NULL OR d.user_status != 'dismissed')")
    if category:
        where.append("d.category=?")
        params.append(category)
    if vendor:
        where.append("LOWER(d.vendor) LIKE ?")
        params.append(f"%{vendor.lower()}%")
    if q:
        like = ("%" + q.replace("%", "\\%").replace("_", "\\_") + "%")
        where.append("(d.title LIKE ? ESCAPE '\\' OR d.description LIKE ? ESCAPE '\\' OR d.promo_code LIKE ? ESCAPE '\\')")
        params.extend([like, like, like])
    if chat_filter:
        marks = ",".join("?" * len(chat_filter))
        where.append(f"d.id IN (SELECT deal_id FROM deal_sources WHERE chat_id IN ({marks}))")
        params.extend(chat_filter)
    # last_seen window (when the offer was posted)
    if from_:
        where.append("d.last_seen >= ?")
        params.append(from_ + "T00:00:00")
    if to:
        where.append("d.last_seen <= ?")
        params.append(to + "T23:59:59")
    if sort == "discount":
        order = "d.discount_pct DESC NULLS LAST"
    elif sort == "price":
        order = "d.price ASC NULLS LAST"
    else:
        order = "d.last_seen DESC"
    clauses = list(where)
    with open_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM deals d WHERE {' AND '.join(clauses)} "
            f"ORDER BY {order} LIMIT ?",
            (*params, min(limit, 500))).fetchall()
        return [_row_to_dict(conn, r) for r in rows]


@router.get("/api/deals/settings")
def deals_settings():
    with open_db() as conn:
        auto = db.get_setting(conn, "deals_auto", "0") == "1"
        watermark = json.loads(db.get_setting(conn, "deals_watermark", "{}") or "{}")
        cats = [r["category"] for r in conn.execute(
            "SELECT DISTINCT category FROM deals WHERE category IS NOT NULL "
            "ORDER BY category").fetchall()]
        vendors = [r["vendor"] for r in conn.execute(
            "SELECT DISTINCT vendor FROM deals WHERE vendor IS NOT NULL "
            "ORDER BY vendor LIMIT 200").fetchall()]
    return {"auto": auto, "categories": cats, "vendors": vendors,
            "watermark": watermark}


@router.get("/api/deals/{deal_id}")
def get_deal(deal_id: int):
    with open_db() as conn:
        r = conn.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()
        if not r:
            return JSONResponse({"error": "deal not found"}, status_code=404)
        return _row_to_dict(conn, r)


class DealPatch(BaseModel):
    user_status: str | None = Field(default=None, max_length=16)
    title: str | None = Field(default=None, max_length=300)
    category: str | None = Field(default=None, max_length=40)
    vendor: str | None = Field(default=None, max_length=120)
    promo_code: str | None = Field(default=None, max_length=80)
    expires: str | None = Field(default=None, max_length=10)
    description: str | None = Field(default=None, max_length=2000)


@router.patch("/api/deals/{deal_id}")
def patch_deal(deal_id: int, req: DealPatch):
    """Human verification: confirm / dismiss / correct fields."""
    if req.user_status is not None and \
            req.user_status not in ("confirmed", "dismissed", None):
        return JSONResponse({"error": "user_status must be confirmed|dismissed"},
                            status_code=400)
    with open_db() as conn:
        if not conn.execute("SELECT 1 FROM deals WHERE id=?",
                            (deal_id,)).fetchone():
            return JSONResponse({"error": "deal not found"}, status_code=404)
        sets, params = ["updated_at=?"], [_now()]
        for field in ("user_status", "title", "category", "vendor",
                      "promo_code", "expires", "description"):
            v = getattr(req, field)
            if v is not None:
                sets.append(f"{field}=?")
                params.append(v.strip() if isinstance(v, str) else v)
        conn.execute(
            f"UPDATE deals SET {', '.join(sets)} WHERE id=?",
            (*params, deal_id))
        conn.commit()
        r = conn.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()
        return _row_to_dict(conn, r)


@router.delete("/api/deals/{deal_id}")
def delete_deal(deal_id: int):
    with open_db() as conn:
        cur = conn.execute("DELETE FROM deals WHERE id=?", (deal_id,))
        conn.commit()
        if cur.rowcount == 0:
            return JSONResponse({"error": "deal not found"}, status_code=404)
    return {"ok": True}


class ManualDeal(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=2000)
    category: str | None = Field(default=None, max_length=40)
    vendor: str | None = Field(default=None, max_length=120)
    discount_pct: float | None = None
    price: float | None = None
    currency: str | None = Field(default=None, max_length=8)
    promo_code: str | None = Field(default=None, max_length=80)
    expires: str | None = Field(default=None, max_length=10)
    chat_id: int | None = None
    msg_id: int | None = None


@router.post("/api/deals")
def add_manual(req: ManualDeal):
    """Manually add a deal: status unverified, human-confirmed by design."""
    now = _now()
    key = deals._identity_key(req.title, req.vendor, req.promo_code, req.price)
    with open_db() as conn:
        if req.chat_id is not None and req.msg_id is not None:
            if not conn.execute(
                    "SELECT 1 FROM messages WHERE chat_id=? AND msg_id=?",
                    (req.chat_id, req.msg_id)).fetchone():
                return JSONResponse(
                    {"error": "source message not found"}, status_code=404)
        cur = conn.execute(
            """INSERT INTO deals (title, description, category, vendor,
                 discount_pct, price, currency, promo_code, expires, status,
                 user_status, confidence, fingerprint, prompt_version, model,
                 first_seen, last_seen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (req.title.strip(), req.description.strip(), req.category,
             req.vendor, req.discount_pct, req.price, req.currency,
             (req.promo_code or "").strip().upper() or None, req.expires,
             "unverified", "confirmed", 1.0, key + "|manual", "manual",
             "human", now, now, now))
        deal_id = cur.lastrowid
        if req.chat_id is not None and req.msg_id is not None:
            conn.execute(
                "INSERT OR IGNORE INTO deal_sources (deal_id, chat_id, msg_id) "
                "VALUES (?,?,?)", (deal_id, req.chat_id, req.msg_id))
        conn.commit()
        r = conn.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()
        return _row_to_dict(conn, r)


class ExtractRequest(BaseModel):
    chat_ids: list[int] = Field(default_factory=list)
    date_from: str | None = Field(default=None, max_length=10)
    date_to: str | None = Field(default=None, max_length=10)


@router.post("/api/deals/extract")
def start_extract(req: ExtractRequest):
    """Queue the visible 'extract' job over a scope (backfill)."""
    if not config.settings.ai_configured:
        return JSONResponse(
            {"error": "AI is not configured - set AI_API_KEY in Settings."},
            status_code=400)
    started = jobs.JOBS.start(
        "extract",
        lambda: jobs.run_extract_job(chat_ids=req.chat_ids or None,
                                     date_from=req.date_from,
                                     date_to=req.date_to))
    return {"started": started, "reason": None if started else "already_queued"}


class AutoRequest(BaseModel):
    enabled: bool


@router.post("/api/deals/auto")
def set_auto(req: AutoRequest):
    """Toggle incremental extraction after each sync (post-sync hook)."""
    with open_db() as conn:
        db.set_setting(conn, "deals_auto", "1" if req.enabled else "0")
        conn.commit()
        return {"auto": req.enabled}
