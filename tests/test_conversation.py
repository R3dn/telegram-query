"""Conversation reconstruction tests (v0.7): reply chain, window,
cycles, and the API context endpoint."""
from datetime import datetime, timezone

import db


def iso(hour):
    return datetime.now(timezone.utc).replace(hour=hour).isoformat()


def seed(conn):
    db.upsert_chat(conn, -1, "Threaded", "threaded", "group")
    # a reply chain: 10 <- 11 <- 12, plus noise around it
    db.upsert_message(conn, -1, 10, iso(10), 1, "ali", "what is the warranty?")
    db.upsert_message(conn, -1, 11, iso(11), 2, "sara",
                      "two years on all models", reply_to=10)
    db.upsert_message(conn, -1, 12, iso(12), 3, "omar",
                      "mine came with 3 years", reply_to=11)
    db.upsert_message(conn, -1, 13, iso(13), 4, "maya", "unrelated comment")
    conn.commit()


def test_conversation_reconstructs_chain_window_and_replies(conn):
    seed(conn)
    ctx = db.conversation(conn, -1, 11, before=1, after=1)
    assert ctx["target"]["msg_id"] == 11
    assert [a["msg_id"] for a in ctx["ancestors"]] == [10]
    assert [r["msg_id"] for r in ctx["replies"]] == [12]
    assert [r["msg_id"] for r in ctx["rows"]] == [10, 11, 12]
    by_id = {r["msg_id"]: r for r in ctx["rows"]}
    assert by_id[11]["is_target"] == 1
    assert by_id[12]["is_reply"] == 1
    assert by_id[10]["is_reply"] == 0
    # window without reply data still shows the neighborhood
    ctx = db.conversation(conn, -1, 13, before=5, after=5)
    assert [r["msg_id"] for r in ctx["rows"]] == [10, 11, 12, 13]
    assert ctx["ancestors"] == [] and ctx["replies"] == []


def test_conversation_is_cycle_safe(conn):
    seed(conn)
    conn.execute("UPDATE messages SET reply_to=10 WHERE chat_id=-1 AND msg_id=10")
    conn.commit()
    ctx = db.conversation(conn, -1, 10)
    assert ctx is not None        # a self-referencing chain must terminate
    assert ctx["target"]["msg_id"] == 10


def test_conversation_missing_message_returns_none(conn):
    seed(conn)
    assert db.conversation(conn, -1, 999) is None
    assert db.conversation(conn, -77, 1) is None


def test_context_endpoint_decorates_rows(api_client):
    conn = db.get_db()
    try:
        db.upsert_chat(conn, -1, "ApiThread", "apithread", "group")
        db.upsert_message(conn, -1, 10, iso(10), 1, "a", "question here?")
        db.upsert_message(conn, -1, 11, iso(11), 2, "b", "the answer",
                          reply_to=10)
        conn.commit()
    finally:
        conn.close()

    r = api_client.get("/api/message/-1/10/context")
    assert r.status_code == 200
    body = r.json()
    assert body["target"]["msg_id"] == 10
    assert body["target"]["chat_title"] == "ApiThread"
    assert body["target"]["tg_link"] == "https://t.me/apithread/10"
    ids = [row["msg_id"] for row in body["rows"]]
    assert 10 in ids and 11 in ids
    assert all("tg_link" in row for row in body["rows"])
    assert any(row["is_reply"] for row in body["rows"])

    r = api_client.get("/api/message/-1/999/context")
    assert r.status_code == 404
    assert r.json()["error"] == "message not found"
