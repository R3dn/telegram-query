"""Export tests: Markdown + JSON, UTF-8/Arabic, citations, no secrets."""
from contextlib import closing
from datetime import datetime, timedelta, timezone

import db


def iso(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def seed(api_client):
    with closing(db.get_db()) as conn:
        db.upsert_chat(conn, -1001234567890, "عروض", "offers", "group")
        db.upsert_message(conn, -1001234567890, 1, iso(1), 1, "سعيد",
                          "عرض خاص اليوم فقط")
        db.upsert_message(conn, -1001234567890, 2, iso(2), 1, "سالم",
                          "expired deal")
        conn.commit()
    api_client.post("/api/bookmarks",
                    json={"chat_id": -1001234567890, "msg_id": 1,
                          "note": "ملاحظة خاصة"})
    api_client.post("/api/bookmarks",
                    json={"chat_id": -1001234567890, "msg_id": 2})


def test_bookmarks_markdown_export(api_client):
    seed(api_client)
    r = api_client.get("/api/export/bookmarks")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert "telegram-query-bookmarks-" in r.headers["content-disposition"]
    body = r.content.decode("utf-8")
    assert "عروض" in body and "عرض خاص اليوم فقط" in body
    assert "ملاحظة خاصة" in body            # note survives
    assert "https://t.me/offers/1" in body  # message link preserved
    assert "شامل" not in body


def test_bookmarks_json_export(api_client):
    seed(api_client)
    r = api_client.get("/api/export/bookmarks?format=json")
    assert r.headers["content-type"].startswith("application/json")
    data = r.json()
    assert data["count"] == 2
    row = next(b for b in data["bookmarks"] if b["msg_id"] == 1)
    assert row["note"] == "ملاحظة خاصة"
    assert row["chat_title"] == "عروض"
    assert row["tg_link"] == "https://t.me/offers/1"
    # no secrets anywhere in the export
    blob = r.content.decode("utf-8")
    for secret in ("test-ai-key", "testhash", "api_key", "session"):
        assert secret not in blob


def test_ai_answer_export_with_sources(api_client):
    seed(api_client)
    r = api_client.post("/api/export/ai-answer", json={
        "question": "شو أفضل عرض؟",
        "answer": "The best deal is **today only** [1].",
        "sources": [
            {"chat_id": -1001234567890, "msg_id": 1},
            {"chat_id": -1001234567890, "msg_id": 999},  # no longer exists
        ],
        "provider_host": "example.internal",
        "model": "test-model",
    })
    assert r.status_code == 200
    body = r.content.decode("utf-8")
    assert "شو أفضل عرض؟" in body
    assert "today only" in body
    assert "https://t.me/offers/1" in body
    assert "no longer available" in body   # missing source is marked, not faked
    assert "test-model" in body           # provenance preserved
