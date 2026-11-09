"""Evidence Explorer API (v0.8.1): the reverse-citation lookup.

"What references this message?" - one endpoint that unifies the whole
citation story: deals, decisions (as source or follow-up), research
briefs, digests, alerts, FAQs (as question or answer), entities, and
the message's own thread context (parent + direct replies, honest about
pre-v0.5 gaps). Read-only, deterministic, local - no AI involved.
"""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse

import db
import deals
import decisions

from . import open_db

router = APIRouter()


def _msg_info(conn, chat_id: int, msg_id: int):
    r = conn.execute(
        """SELECT m.chat_id, m.msg_id, m.text, m.date, m.sender_name,
                  m.reply_to, c.title AS chat_title, c.username AS chat_username
           FROM messages m JOIN chats c ON c.chat_id = m.chat_id
           WHERE m.chat_id=? AND m.msg_id=?""",
        (chat_id, msg_id)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["tg_link"] = db.message_link(d["chat_id"], d.pop("chat_username"),
                                   d["msg_id"])
    return d


@router.get("/api/evidence")
def evidence(chat_id: int, msg_id: int):
    """Everything in the archive that references one message."""
    with open_db() as conn:
        message = _msg_info(conn, chat_id, msg_id)
        if not message:
            return JSONResponse({"error": "message not found"},
                                status_code=404)
        refs: dict[str, list] = {}

        # deals
        raw_deals = [dict(r) for r in conn.execute(
            """SELECT d.id, d.title, d.vendor, d.status,
                      d.user_status, d.confidence, d.expires, d.valid_from
               FROM deal_sources s JOIN deals d ON d.id = s.deal_id
               WHERE s.chat_id=? AND s.msg_id=?""",
            (chat_id, msg_id)).fetchall()]
        for d in raw_deals:
            d["derived_status"] = deals.derived_status(d)
            d["confidence_label"] = deals.confidence_label(d.get("confidence"))
        refs["deals"] = raw_deals

        # decisions: citations + follow-ups
        src = [dict(r) for r in conn.execute(
            """SELECT d.id, d.title, d.kind, d.owner, d.due_date,
                      d.status, d.user_status, d.confidence
               FROM decision_sources s JOIN decisions d ON d.id = s.decision_id
               WHERE s.chat_id=? AND s.msg_id=?""",
            (chat_id, msg_id)).fetchall()]
        fu = [dict(r) for r in conn.execute(
            """SELECT d.id, d.title, d.kind, d.owner, d.due_date,
                      d.status, d.user_status, d.confidence,
                      f.matched_terms
               FROM decision_followups f
                    JOIN decisions d ON d.id = f.decision_id
               WHERE f.chat_id=? AND f.msg_id=?""",
            (chat_id, msg_id)).fetchall()]
        for d in src:
            d["as"] = "source"
        for d in fu:
            d["as"] = "followup"
            d["matched_terms"] = json.loads(d.get("matched_terms") or "[]")
        for d in src + fu:
            d["derived_status"] = decisions.derived_status(d)
            d["confidence_label"] = decisions.confidence_label(
                d.get("confidence"))
        refs["decisions"] = src + fu

        # research briefs (via version citations)
        refs["briefs"] = [dict(r) for r in conn.execute(
            """SELECT DISTINCT b.id, b.question, v.version, v.created_at
               FROM brief_citations c
                    JOIN brief_versions v ON v.id = c.version_id
                    JOIN briefs b         ON b.id = v.brief_id
               WHERE c.chat_id=? AND c.msg_id=?
               ORDER BY v.created_at DESC""",
            (chat_id, msg_id)).fetchall()]

        # digests
        refs["digests"] = [dict(r) for r in conn.execute(
            """SELECT DISTINCT g.id, g.period_start, g.period_end,
                      g.schedule_id, g.created_at
               FROM digest_citations c JOIN digests g ON g.id = c.digest_id
               WHERE c.chat_id=? AND c.msg_id=?
               ORDER BY g.created_at DESC""",
            (chat_id, msg_id)).fetchall()]

        # alerts
        refs["alerts"] = [dict(r) for r in conn.execute(
            """SELECT a.id, a.matched_term, a.created_at, a.read,
                      w.name AS watchlist_name
               FROM alerts a JOIN watchlists w ON w.id = a.watchlist_id
               WHERE a.chat_id=? AND a.msg_id=?""",
            (chat_id, msg_id)).fetchall()]

        # FAQs (JSON source lists - question side and answer side)
        faqs: list[dict] = []
        for f in conn.execute(
                "SELECT id, question, status, frequency, source_questions, "
                "source_answers FROM faq_clusters").fetchall():
            for col, as_ in (("source_questions", "question"),
                             ("source_answers", "answer")):
                try:
                    items = json.loads(f[col] or "[]")
                except (ValueError, TypeError):
                    items = []
                for it in items:
                    if isinstance(it, dict) and \
                            it.get("chat_id") == chat_id and \
                            it.get("msg_id") == msg_id:
                        faqs.append({"id": f["id"], "question": f["question"],
                                     "status": f["status"],
                                     "frequency": f["frequency"], "as": as_})
                        break
        refs["faqs"] = faqs

        # entities
        refs["entities"] = [dict(r) for r in conn.execute(
            """SELECT e.id, e.name, e.kind, e.ignored
               FROM entity_mentions m JOIN entities e ON e.id = m.entity_id
               WHERE m.chat_id=? AND m.msg_id=?""",
            (chat_id, msg_id)).fetchall()]

        # thread context (captured going forward - v0.5+ reply_to)
        parent = None
        if message.get("reply_to") is not None:
            parent = _msg_info(conn, chat_id, int(message["reply_to"]))
        replies = [_msg_info(conn, chat_id, r["msg_id"]) for r in
                   conn.execute(
                       "SELECT msg_id FROM messages WHERE chat_id=? "
                       "AND reply_to=? ORDER BY msg_id LIMIT 20",
                       (chat_id, msg_id)).fetchall()]
        thread = {"parent": parent, "replies": replies}

        total = sum(len(v) for v in refs.values())
        return {"message": message, "references": refs, "thread": thread,
                "total": total}
