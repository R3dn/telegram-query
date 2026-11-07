"""Topic watchlists (v0.6): keyword monitors over each sync's new messages.

DETERMINISTIC BY DESIGN: matching uses the stored text_norm (the same
normalized form search uses) - the LLM is never called, so watchlists keep
working without an AI provider and cost nothing per message.

Pipeline (after each sync, or on demand):
  1. New messages per chat = msg_id above the per-chat watermark.
  2. Every enabled watchlist evaluates its terms (+ exclusions, group
     scope) against those messages.
  3. Matching messages become alerts (UNIQUE per watchlist+message -
     reposts can never duplicate).
  4. The watermark advances to the newest stored message per chat, so the
     next run only ever looks at genuinely new messages.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import db

__all__ = ["evaluate_new", "post_sync_hook", "unread_count"]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _terms(raw: str) -> list[str]:
    try:
        vals = json.loads(raw or "[]")
    except ValueError:
        vals = []
    return [db.normalize_text(v) for v in vals if isinstance(v, str) and v.strip()]


def evaluate_new(conn, verbose=print) -> dict:
    """Run all enabled watchlists over messages above the watermark."""
    stats = {"new_messages": 0, "matches": 0, "watchlists": 0}
    watches = conn.execute(
        "SELECT * FROM watchlists WHERE enabled=1").fetchall()
    if not watches:
        return stats
    stats["watchlists"] = len(watches)

    marks = {r["chat_id"]: r["last_msg_id"] for r in conn.execute(
        "SELECT chat_id, last_msg_id FROM watch_watermarks").fetchall()}
    chats = [c["chat_id"] for c in db.get_tracked_chats(conn)]

    new_rows = []
    for cid in chats:
        floor = marks.get(cid, 0)
        rows = conn.execute(
            """SELECT m.chat_id, m.msg_id, m.text, m.text_norm, m.date
               FROM messages m WHERE m.chat_id=? AND m.msg_id > ?
               ORDER BY m.msg_id""",
            (cid, floor)).fetchall()
        new_rows.extend(rows)
    stats["new_messages"] = len(new_rows)

    now = _now()
    for w in watches:
        terms = _terms(w["terms"])
        excludes = _terms(w["exclude_terms"])
        scope = json.loads(w["chat_ids"] or "[]")
        if not terms:
            continue
        matched_any = False
        for r in new_rows:
            if scope and r["chat_id"] not in scope:
                continue
            text_norm = r["text_norm"] or ""
            if not text_norm:
                continue
            if any(ex in text_norm for ex in excludes):
                continue
            hit = next((t for t in terms if t in text_norm), None)
            if hit is None:
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO alerts (watchlist_id, chat_id, msg_id, "
                "matched_term, created_at) VALUES (?,?,?,?,?)",
                (w["id"], r["chat_id"], r["msg_id"], hit[:100], now))
            stats["matches"] += cur.rowcount
            matched_any = True
        if matched_any:
            conn.execute("UPDATE watchlists SET last_match_at=? WHERE id=?",
                         (now, w["id"]))

    # advance watermarks once, to the newest stored message per chat
    for cid in chats:
        hi = conn.execute(
            "SELECT COALESCE(MAX(msg_id), 0) m FROM messages WHERE chat_id=?",
            (cid,)).fetchone()["m"]
        conn.execute(
            "INSERT INTO watch_watermarks (chat_id, last_msg_id) VALUES (?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET last_msg_id=excluded.last_msg_id",
            (cid, hi))
    conn.commit()
    if stats["matches"]:
        verbose(f"[watchlists] {stats['matches']} new alert(s) from "
                f"{stats['new_messages']} new message(s)")
    return stats


def unread_count(conn) -> int:
    return conn.execute(
        "SELECT COUNT(*) c FROM alerts WHERE read=0 AND archived=0"
    ).fetchone()["c"]


def post_sync_hook():
    """Registered in app.py: evaluate new messages after every sync."""
    conn = db.get_db()
    try:
        if conn.execute("SELECT COUNT(*) c FROM watchlists").fetchone()["c"]:
            evaluate_new(conn)
    except Exception as e:  # noqa: BLE001 - never fails the sync
        print(f"[watchlists] post-sync evaluation failed: {e}")
    finally:
        conn.close()
