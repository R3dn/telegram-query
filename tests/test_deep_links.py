"""Telegram deep-link tests: verified formats, no fabricated URLs."""
from contextlib import closing

import db


def test_public_username_link():
    assert db.message_link(-123, "dealz", 456) == "https://t.me/dealz/456"


def test_private_supergroup_link():
    # Telethon marks supergroups/channels as -1000000000000 - <id>
    assert db.message_link(-1001234567890, None, 77) == \
        "https://t.me/c/1234567890/77"


def test_basic_group_has_no_link():
    assert db.message_link(-40, None, 1) is None


def test_user_chat_has_no_link():
    assert db.message_link(12345, None, 1) is None


def test_missing_ids_are_safe():
    assert db.message_link(None, "dealz", 5) == "https://t.me/dealz/5"
    assert db.message_link(-123, None, None) is None
    assert db.message_link(None, None, None) is None


def test_api_decorates_rows(api_client):
    with closing(db.get_db()) as conn:
        db.upsert_chat(conn, -1001234567890, "Dealz", "dealz", "group")
        db.upsert_chat(conn, -1009999999999, "Private corner", None, "channel")
        db.upsert_chat(conn, -77, "Old basic group", None, "group")
        db.upsert_message(conn, -1001234567890, 1, "2026-01-01T10:00:00+00:00",
                          1, "s", "public message")
        db.upsert_message(conn, -1009999999999, 1, "2026-01-01T10:00:00+00:00",
                          1, "s", "private channel message")
        db.upsert_message(conn, -77, 1, "2026-01-01T10:00:00+00:00",
                          1, "s", "basic group message")
        conn.commit()

    page = api_client.get("/api/messages").json()["messages"]
    links = {m["chat_id"]: m["tg_link"] for m in page}
    assert links[-1001234567890] == "https://t.me/dealz/1"
    assert links[-1009999999999] == "https://t.me/c/9999999999/1"
    assert links[-77] is None

    one = api_client.get("/api/message/-1001234567890/1").json()
    assert one["tg_link"] == "https://t.me/dealz/1"
    assert "chat_username" not in one, "internal helper must not leak"
