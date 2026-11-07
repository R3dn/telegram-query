"""Exports (v0.4): Markdown + JSON downloads of user knowledge.

Exports are useful OUTSIDE the app: valid UTF-8, Arabic-safe, message
references + timestamps + citations preserved, safe ASCII filenames, and
never any secrets (no credentials, no session data).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

import db
from api import open_db

router = APIRouter()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _download(content: str, filename: str, media_type: str) -> Response:
    # filename is always built here from a fixed prefix + date: ASCII-safe
    return Response(
        content=content,
        media_type=f"{media_type}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _md_escape(text: str) -> str:
    return (text or "").replace("\\", "\\\\").strip()


@router.get("/api/export/bookmarks")
def export_bookmarks(format: str = "md"):
    """All bookmarks + notes, grouped by chat, newest first."""
    with open_db() as conn:
        rows = [dict(r) for r in conn.execute(
            """
            SELECT b.note, m.chat_id, m.msg_id, m.date, m.sender_name, m.text,
                   m.has_media, c.title AS chat_title, c.username AS chat_username
            FROM bookmarks b
            JOIN messages m ON m.chat_id = b.chat_id AND m.msg_id = b.msg_id
            JOIN chats c   ON c.chat_id = m.chat_id
            ORDER BY c.title COLLATE NOCASE, m.date DESC
            """).fetchall()]
    for r in rows:
        r["tg_link"] = db.message_link(r["chat_id"], r["chat_username"],
                                       r["msg_id"])

    if format == "json":
        data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "count": len(rows),
            "bookmarks": [{k: v for k, v in r.items()} for r in rows],
        }
        return _download(json.dumps(data, ensure_ascii=False, indent=2),
                         f"telegram-query-bookmarks-{_today()}.json",
                         "application/json")

    lines = ["# Telegram Query - Bookmarks",
             "",
             f"Exported {_today()} (UTC) - {len(rows)} bookmark(s).",
             ""]
    last_chat = None
    for r in rows:
        if r["chat_title"] != last_chat:
            lines.append(f"\n## {_md_escape(r['chat_title'])}\n")
            last_chat = r["chat_title"]
        date = (r["date"] or "")[:10]
        lines.append(f"**{date} - {_md_escape(r['sender_name'] or 'unknown')}**"
                     f" (msg {r['msg_id']})")
        if r["text"]:
            for ln in (r["text"] or "").splitlines() or [""]:
                lines.append(f"> {ln}")
        if r["has_media"]:
            lines.append("_[attached media]_")
        if r["note"]:
            lines.append(f"Note: {_md_escape(r['note'])}")
        if r["tg_link"]:
            lines.append(f"[Open in Telegram]({r['tg_link']})")
        lines.append("")
    return _download("\n".join(lines),
                     f"telegram-query-bookmarks-{_today()}.md", "text/markdown")


@router.get("/api/export/saved-searches")
def export_saved_searches():
    """Saved searches as importable/inspectable JSON (definition, not rows)."""
    from api.saved import _row_to_dict
    with open_db() as conn:
        rows = conn.execute("SELECT * FROM saved_searches").fetchall()
    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "saved_searches": [_row_to_dict(r) for r in rows],
    }
    return _download(json.dumps(data, ensure_ascii=False, indent=2),
                     f"telegram-query-saved-searches-{_today()}.json",
                     "application/json")


class AiExportRequest(BaseModel):
    question: str = Field(max_length=2000)
    answer: str = Field(max_length=100_000)
    sources: list[dict] = Field(default_factory=list)
    provider_host: str = Field(default="", max_length=200)
    model: str = Field(default="", max_length=200)


@router.post("/api/export/ai-answer")
def export_ai_answer(req: AiExportRequest):
    """Render an AI answer + its sources as Markdown.

    Source rows are re-fetched from the archive so the export shows exactly
    what the citation pointed at (or marks it unavailable)."""
    with open_db() as conn:
        rows = []
        for s in (req.sources or [])[:200]:
            r = conn.execute(
                """SELECT m.chat_id, m.msg_id, m.date, m.sender_name, m.text,
                          m.has_media, c.title AS chat_title,
                          c.username AS chat_username
                   FROM messages m JOIN chats c ON c.chat_id = m.chat_id
                   WHERE m.chat_id=? AND m.msg_id=?""",
                (s.get("chat_id"), s.get("msg_id"))).fetchone()
            if r:
                d = dict(r)
                d["tg_link"] = db.message_link(d["chat_id"],
                                                d["chat_username"],
                                                d["msg_id"])
            else:
                d = None
            rows.append(d)

    lines = ["# Telegram Query - AI answer", "",
             f"Question: {req.question}", "",
             f"_Generated {_today()} (UTC)"
             f"{f' by {req.model} via {req.provider_host}' if req.model else ''}_",
             "", req.answer, "", "## Sources", ""]
    for i, r in enumerate(rows, 1):
        if r is None:
            lines.append(f"{i}. _[message no longer available in the archive]_")
            continue
        date = (r["date"] or "")[:10]
        lines.append(f"{i}. **{_md_escape(r['chat_title'])} - {date}** "
                     f"- {_md_escape(r['sender_name'] or 'unknown')}")
        for ln in (r["text"] or "").splitlines()[:8] or [""]:
            lines.append(f"   > {ln}")
        if r["tg_link"]:
            lines.append(f"   [Open in Telegram]({r['tg_link']})")
    return _download("\n".join(lines),
                     f"telegram-query-ai-answer-{_today()}.md", "text/markdown")


@router.get("/api/export/deals")
def export_deals(format: str = "md"):
    """All deals + their sources (structured knowledge records)."""
    import deals as deals_mod
    with open_db() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM deals ORDER BY last_seen DESC").fetchall()]
        sources = {}
        for d in rows:
            src = conn.execute(
                """SELECT s.chat_id, s.msg_id, m.text, m.date, m.sender_name,
                          c.title AS chat_title, c.username AS chat_username
                   FROM deal_sources s
                   LEFT JOIN messages m ON m.chat_id = s.chat_id AND m.msg_id = s.msg_id
                   LEFT JOIN chats c   ON c.chat_id = m.chat_id
                   WHERE s.deal_id=? ORDER BY m.date DESC""", (d["id"],)).fetchall()
            sources[d["id"]] = []
            for s in src:
                sd = dict(s)
                sd["tg_link"] = db.message_link(
                    sd["chat_id"], sd.pop("chat_username"), sd["msg_id"])
                sources[d["id"]].append(sd)
            d["derived_status"] = deals_mod.derived_status(d)
            d["confidence_label"] = deals_mod.confidence_label(d.get("confidence"))

    if format == "json":
        for d in rows:
            d["sources"] = sources[d["id"]]
        data = {"exported_at": datetime.now(timezone.utc).isoformat(),
                "count": len(rows), "deals": rows}
        return _download(json.dumps(data, ensure_ascii=False, indent=2),
                         f"telegram-query-deals-{_today()}.json",
                         "application/json")

    lines = ["# Telegram Query - Deals", "",
             f"Exported {_today()} (UTC) - {len(rows)} deal(s).", ""]
    for d in rows:
        bits = [f"## {d['title']}"]
        meta = []
        if d.get("vendor"):
            meta.append(f"vendor: {d['vendor']}")
        if d.get("promo_code"):
            meta.append(f"code: **{d['promo_code']}**")
        if d.get("discount_pct") is not None:
            meta.append(f"{d['discount_pct']:g}% off")
        if d.get("price") is not None:
            meta.append(f"{d['price']:g} {d.get('currency') or ''}".strip())
        if d.get("expires"):
            meta.append(f"expires: {d['expires']}")
        meta.append(f"status: {d['derived_status']}"
                    + (" (confirmed)" if d.get("user_status") == "confirmed" else ""))
        bits.append(" · ".join(meta))
        if d.get("description"):
            bits.append(f"\n{d['description']}")
        for s in sources[d["id"]]:
            date = (s["date"] or "")[:10]
            src_txt = (s["text"] or "").splitlines()
            first = src_txt[0][:140] if src_txt else "[no text]"
            bits.append(f"- {_md_escape(s['chat_title'] or '?')} · {date}: "
                        f"{_md_escape(first)}"
                        + (f" ([Telegram]({s['tg_link']}))" if s["tg_link"] else ""))
        lines.append("\n".join(bits) + "\n")
    return _download("\n".join(lines),
                     f"telegram-query-deals-{_today()}.md", "text/markdown")


@router.get("/api/export/briefs/{brief_id}")
def export_brief(brief_id: int, format: str = "md"):
    """One research brief + validated citations + metadata."""
    import research
    with open_db() as conn:
        brief = research.get_brief(conn, brief_id)
        if not brief:
            return JSONResponse({"error": "brief not found"}, status_code=404)
        ver = research.latest_version(conn, brief_id)
        if not ver:
            return JSONResponse(
                {"error": "this brief has no generated version yet"},
                status_code=400)
        citations = research.version_citations(conn, ver["id"])
        scope = json.loads(brief["chat_ids"] or "[]")
        stale = research.staleness(conn, brief_id)

    if format == "json":
        data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "brief": {
                "id": brief["id"], "question": brief["question"],
                "chat_ids": scope, "date_from": brief["date_from"],
                "date_to": brief["date_to"], "notes": brief["notes"],
                "created_at": brief["created_at"],
                "updated_at": brief["updated_at"],
            },
            "version": {
                "version": ver["version"], "answer_md": ver["answer_md"],
                "keywords": json.loads(ver["keywords"] or "[]"),
                "model": ver["model"], "prompt_version": ver["prompt_version"],
                "created_at": ver["created_at"],
            },
            "stale_count": stale,
            "citations": [{k: v for k, v in c.items()} for c in citations],
        }
        return _download(json.dumps(data, ensure_ascii=False, indent=2),
                         f"telegram-query-brief-{brief_id}-{_today()}.json",
                         "application/json")

    scope_txt = f"{len(scope)} group(s)"
    if brief["date_from"] or brief["date_to"]:
        scope_txt += f" · {brief['date_from'] or '…'} → {brief['date_to'] or '…'}"
    lines = ["# Telegram Query - Research brief", "",
             f"## {brief['question']}", "",
             f"_Version {ver['version']} · generated {ver['created_at'][:10]} "
             f"by {ver['model']} · staleness: "
             f"{stale} new matching message(s) since_",
             f"_Scope: {scope_txt}_", ""]
    lines.append(ver["answer_md"])
    lines += ["", "## Citations", ""]
    for c in citations:
        date = (c["date"] or "")[:10]
        lines.append(f"[{c['idx']}] **{_md_escape(c['chat_title'])} · {date} · "
                     f"{_md_escape(c['sender_name'] or 'unknown')}**"
                     + (f" ([Telegram]({c['tg_link']}))" if c.get("tg_link") else ""))
        for ln in (c["text"] or "").splitlines()[:4] or [""]:
            lines.append(f"> {ln}")
    return _download("\n".join(lines),
                     f"telegram-query-brief-{brief_id}-{_today()}.md",
                     "text/markdown")
