"""AI question-answering over stored Telegram messages.

Pipeline (keyword + retry):
  1. LLM extracts keywords/phrases + optional filters (chat titles, date range)
     from the user question. Bilingual (English/Arabic) aware.
  2. FTS5 search. If results look weak, LLM proposes alternative keywords
     (max 2 retries).
  3. LLM answers the question in the question's language, citing [n] sources.
"""
import json
import os
from datetime import datetime, timedelta, timezone

import db
from openai import OpenAI

SYSTEM_EXTRACT = """You extract search keywords from a question about Telegram group messages.
Groups contain coupon/deal posts in MIXED English and Arabic (often with Hebrew brand names too).
Return ONLY a JSON object, no markdown:
{{
 "keywords": ["restaurant name", "variant spelling", ...],   // 2-6 short search phrases
 "chat_titles": ["exact group titles to restrict to", ...],    // [] if question is about all groups
 "date_from": "YYYY-MM-DD or null",
 "date_to": "YYYY-MM-DD or null",
 "relative_days": null                                          // int if question says "last N days" etc
}}
Rules:
- Keywords must cover BOTH English and Arabic/translated spellings if plausible (e.g. "mcdonalds" and "ماكدونالدز").
- Include likely spelling variants of proper names as separate keywords.
- Prefer 1-3 word phrases over single letters.
- Resolve relative dates using the provided current date.
Today's date (UTC): {today}"""

SYSTEM_ANSWER = """You answer questions about coupon/deal messages from Telegram groups.
Given numbered message excerpts, answer the user's question:
- CRITICAL: answer in the SAME LANGUAGE as the user's question. English question -> English answer. Arabic question -> Arabic answer. Never switch to the messages' language.
- List each relevant coupon/deal: business name, the offer, expiry/code if present, which group, date.
- A "code" is only an actual promotional/code token users type in (e.g. MCD30, ALINMA). Do NOT list prices, amounts, or random words as codes. If a code is missing, say so.
- Cite messages as [n] after each claim, e.g. "20% off at X [2]".
- Merge duplicates: if multiple messages describe the same deal, list it once with all citations.
- If the excerpts don't contain the answer, say so honestly. Do NOT invent deals.
- Ignore expired coupons only if the question implies currently-valid deals."""

SYSTEM_RETRY = """The previous keywords found too few Telegram messages. Given the question and
the keyword sets already tried, propose ONE new set of alternative keywords
(different spellings, translations, related brand/product words).
Return ONLY a JSON object: {{"keywords": [...], "chat_titles": [], "date_from": null, "date_to": null, "relative_days": null}}
Today's date (UTC): {today}"""


def is_configured():
    return bool(os.environ.get("AI_API_KEY"))


def get_client():
    return OpenAI(
        api_key=os.environ["AI_API_KEY"],
        base_url=os.environ.get("AI_BASE_URL") or None,
    )


def _chat(client, system, user, model=None):
    resp = client.chat.completions.create(
        model=model or os.environ.get("AI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.2,
    )
    return resp.choices[0].message.content


def _parse_json(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw.strip())
    except Exception:
        return None


def _resolve_dates(spec, today):
    date_from = spec.get("date_from")
    date_to = spec.get("date_to")
    rel = spec.get("relative_days")
    if rel and not date_from:
        try:
            date_from = (today - timedelta(days=int(rel))).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            pass
    return date_from, date_to


def _resolve_chat_ids(conn, titles):
    ids = []
    for t in (titles or []):
        t = (t or "").strip()
        if not t:
            continue
        row = conn.execute(
            "SELECT chat_id FROM chats WHERE tracked=1 AND LOWER(title)=LOWER(?)",
            (t,),
        ).fetchone()
        if row:
            ids.append(row["chat_id"])
        else:
            like = conn.execute(
                "SELECT chat_id FROM chats WHERE tracked=1 AND LOWER(title) LIKE ?",
                (f"%{t.lower()}%",),
            ).fetchall()
            ids.extend(r["chat_id"] for r in like)
    return sorted(set(ids)) or None


def _format_messages(rows):
    lines = []
    for i, m in enumerate(rows, 1):
        date = (m["date"] or "")[:10]
        sender = m["sender_name"] or "unknown"
        text = (m["text"] or "").strip() or "[no text / media only]"
        if m["has_media"] and text != "[no text / media only]":
            text += " [has image]"
        lines.append(f"[{i}] ({m['chat_title']}, {date}, by {sender}): {text}")
    return "\n".join(lines)


def _dedupe(rows):
    """Near-duplicate collapse: same first 80 norm chars + same date = same deal repost."""
    seen = set()
    out = []
    for r in rows:
        key = (r["text"] or "")[:80].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def ask(conn, question, max_results=60):
    """Full pipeline. Returns dict(answer, sources, attempts, keywords_tried)."""
    if not is_configured():
        return {"answer": None,
                "error": "AI not configured - set AI_API_KEY in .env",
                "sources": [], "attempts": 0, "keywords_tried": []}

    client = get_client()
    today = datetime.now(timezone.utc).date()
    tried_keyword_sets = []
    all_rows = {}      # (chat_id, msg_id) -> row, unioned across attempts
    best_rows = []     # rows from the most successful attempt
    attempts = 0
    spec = None

    while attempts <= 2:  # initial + 2 retries
        attempts += 1
        if attempts == 1:
            system = SYSTEM_EXTRACT.format(today=today)
            user = question
        else:
            prev = "; ".join("[" + ", ".join(k) + "]" for k in tried_keyword_sets)
            system = SYSTEM_RETRY.format(today=today)
            user = (f"Question: {question}\n"
                    f"Keyword sets already tried: {prev}\n"
                    f"Results found so far: {len(best_rows)}")

        raw = _chat(client, system, user)
        spec = _parse_json(raw) or {}
        kws = [k for k in (spec.get("keywords") or []) if k and k.strip()]
        if not kws:
            break
        tried_keyword_sets.append(kws)

        date_from, date_to = _resolve_dates(spec, today)
        chat_ids = _resolve_chat_ids(conn, spec.get("chat_titles"))
        if chat_ids == []:
            chat_ids = None

        rows = db.search(
            conn, kws, chat_ids=chat_ids,
            date_from=date_from, date_to=date_to,
            require_all=False,  # OR: any variant hit counts
            limit=200,
        )
        # union across attempts so retries never lose earlier hits
        for r in rows:
            key = (r["chat_id"], r["msg_id"])
            if key not in all_rows:
                all_rows[key] = r
        if len(rows) > len(best_rows):
            best_rows = rows
        if len(all_rows) >= 3:
            break

    rows = _dedupe(list(all_rows.values()))[:max_results]

    if not rows:
        return {"answer": ("I couldn't find any messages matching that. "
                           "Try different wording, or sync more groups."),
                "sources": [], "attempts": attempts,
                "keywords_tried": tried_keyword_sets}

    context = _format_messages(rows)
    answer = _chat(
        client, SYSTEM_ANSWER,
        f"Today: {today}\n\nQuestion: {question}\n\nMessages:\n{context}",
    )
    return {"answer": answer, "sources": rows, "attempts": attempts,
            "keywords_tried": tried_keyword_sets}
