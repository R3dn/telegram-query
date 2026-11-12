"""API tests: endpoint contracts, empty states, security invariants."""
import db


def seed(api_client):
    c = db.get_db()
    try:
        db.upsert_chat(c, -1, "Test Group", "testgrp", "group")
        db.upsert_message(c, -1, 1, "2026-01-01T10:00:00+00:00",
                          1, "alice", "pizza deal عرض")
        c.commit()
    finally:
        c.close()


def test_health_and_state(api_client):
    r = api_client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True
    r = api_client.get("/api/app/state")
    body = r.json()
    assert body["telegram_configured"] is True
    assert body["ai_configured"] is True
    # secrets must never appear in any state payload
    assert "test-ai-key" not in r.text
    assert "testhash" not in r.text


def test_empty_archive_flow(api_client):
    """A brand-new install: endpoints work with an empty DB."""
    assert api_client.get("/api/groups").json() == []
    r = api_client.get("/api/messages?limit=10")
    body = r.json()
    assert body == {"messages": [], "next_cursor": None, "has_more": False}
    assert api_client.get("/api/senders").json() == []
    assert api_client.get("/api/search?q=anything").json() == []


def test_browse_search_senders(api_client):
    seed(api_client)
    body = api_client.get("/api/messages?limit=10").json()
    assert len(body["messages"]) == 1
    assert body["messages"][0]["chat_title"] == "Test Group"

    hits = api_client.get("/api/search?q=%D8%B9%D8%B1%D8%B6").json()  # عرض
    assert len(hits) == 1

    senders = api_client.get("/api/senders?groups=-1").json()
    assert senders[0]["sender_name"] == "alice"


def test_search_media_filter(api_client):
    """v1.0.2 regression: the FilterBar media control is shown in search
    mode, so /api/search must honor it (it used to be silently ignored
    while the chip looked active)."""
    c = db.get_db()
    try:
        db.upsert_chat(c, -1, "Test Group", "testgrp", "group")
        db.upsert_message(c, -1, 1, "2026-01-01T10:00:00+00:00",
                          1, "alice", "pizza deal عرض", has_media=0)
        db.upsert_message(c, -1, 2, "2026-01-01T10:01:00+00:00",
                          1, "bob", "pizza deal عرض", has_media=1)
        c.commit()
    finally:
        c.close()

    hits = api_client.get("/api/search?q=pizza").json()
    assert len(hits) == 2, "unfiltered search sees both messages"
    hits = api_client.get("/api/search?q=pizza&media=1").json()
    assert len(hits) == 1 and hits[0]["has_media"] == 1, \
        "media=1 keeps only image messages"
    hits = api_client.get("/api/search?q=pizza&media=0").json()
    assert len(hits) == 1 and hits[0]["has_media"] == 0, \
        "media=0 keeps only text messages"
    r = api_client.get("/api/search?q=pizza&media=2")
    assert r.status_code == 400, \
        "an invalid media value is an honest error, never a silent filter drop"
    r = api_client.get("/api/messages?media=5")
    assert r.status_code == 400, "browse validates media the same way"


def test_search_rejects_negative_limits(api_client):
    """v1.0.2 regression: a negative limit used to become SQLite's
    LIMIT -1 (unbounded) - one request could fetch the entire archive."""
    seed(api_client)
    r = api_client.get("/api/search?q=pizza&limit=-1")
    assert r.status_code == 200
    assert len(r.json()) == 1, "the cap must hold for any limit value"
    r = api_client.get("/api/messages?limit=-1")
    assert r.status_code == 200 and r.json()["messages"] != [], \
        "browse clamps negative limits instead of returning an empty page"


def test_single_message_endpoint(api_client):
    seed(api_client)
    m = api_client.get("/api/message/-1/1")
    assert m.status_code == 200 and m.json()["text"].startswith("pizza")
    assert api_client.get("/api/message/-1/999").status_code == 404


def test_ask_validation(api_client, monkeypatch):
    # no AI key -> clean 400
    import config
    monkeypatch.setattr(config.settings, "ai_api_key", "")
    r = api_client.post("/api/ask", json={"question": "hello"})
    assert r.status_code == 400
    assert "AI_API_KEY" in r.json()["error"]

    # key restored; oversized question rejected by pydantic
    monkeypatch.setattr(config.settings, "ai_api_key", "test-ai-key")
    r = api_client.post("/api/ask", json={"question": "x" * 5000})
    assert r.status_code == 422

    # empty question rejected
    r = api_client.post("/api/ask", json={"question": "   "})
    assert r.status_code == 400


def test_untrack_requires_ids(api_client):
    assert api_client.post("/api/groups/untrack", json={"chat_ids": []}).status_code == 400


def test_untrack_keeps_messages_by_default(api_client):
    seed(api_client)
    c = db.get_db()
    try:
        db.update_sync_state(c, -1, 1)   # pretend one sync already ran
        c.commit()
    finally:
        c.close()

    r = api_client.post("/api/groups/untrack", json={"chat_ids": [-1]})
    assert r.json() == {"ok": True, "deleted_messages": False}

    # hidden from browse/search/stats, but rows remain on disk
    assert api_client.get("/api/messages?limit=10").json()["messages"] == []
    assert api_client.get("/api/search?q=pizza").json() == []
    assert api_client.get("/api/stats").json()["messages"] == 0
    c = db.get_db()
    try:
        n = c.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
        state = db.get_sync_state(c, -1)
    finally:
        c.close()
    assert n == 1, "default untrack must keep message rows"
    assert state[0] == 1, "default untrack must keep the sync high-water mark"


def test_untrack_delete_messages(api_client):
    seed(api_client)
    c = db.get_db()
    try:
        c.execute("UPDATE chats SET last_msg_id=1, backfill_floor=0 "
                  "WHERE chat_id=-1")
        c.commit()
    finally:
        c.close()

    r = api_client.post("/api/groups/untrack",
                        json={"chat_ids": [-1], "delete_messages": True})
    assert r.json() == {"ok": True, "deleted_messages": True}

    c = db.get_db()
    try:
        n = c.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
        state = db.get_sync_state(c, -1)
        hits = db.search(c, ["pizza deal"])
    finally:
        c.close()
    assert n == 0, "delete_messages must remove the rows"
    assert state[0] == 0 and state[2] == 0, "sync state must reset (re-track re-backfills)"
    assert hits == [], "FTS must not return deleted messages"


def test_stats_counts_tracked_only(api_client):
    seed(api_client)
    c = db.get_db()
    try:
        db.upsert_chat(c, -2, "Other", None, "group")
        db.upsert_message(c, -2, 1, "2026-01-05T10:00:00+00:00",
                          1, "bob", "second group message")
        c.commit()
    finally:
        c.close()
    assert api_client.get("/api/stats").json()["messages"] == 2

    api_client.post("/api/groups/untrack", json={"chat_ids": [-2]})
    assert api_client.get("/api/stats").json()["messages"] == 1


def test_track_without_credentials(api_client, monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "tg_api_id", "")
    r = api_client.post("/api/groups/track", json={"chat_ids": [-1]})
    assert r.status_code == 400
    assert "TG_API_ID" in r.json()["error"]


def test_job_status_shape(api_client):
    body = api_client.get("/api/job/status").json()
    assert set(body) >= {"running", "name", "log", "queued", "last_done"}


def test_stop_with_nothing_running(api_client):
    body = api_client.post("/api/job/stop", json={"clear_queue": True}).json()
    assert body["stopping"] is False and body["cleared"] == []
