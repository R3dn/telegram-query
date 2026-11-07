"""Watchlists tests: deterministic matching, watermarks, dedupe, API."""
from datetime import datetime, timedelta, timezone

import db
import watchlists


def iso(days_ago, hour=10):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)
            ).replace(hour=hour).isoformat()


def seed(conn, with_msgs=True):
    db.upsert_chat(conn, -1, "Tech talk", "techtalk", "group")
    db.upsert_chat(conn, -2, "Cars", None, "group")
    if with_msgs:
        db.upsert_message(conn, -1, 1, iso(3), 1, "a", "kubernetes migration guide")
        db.upsert_message(conn, -1, 2, iso(2), 1, "b", "anyone knows kubernetes pricing?")
        db.upsert_message(conn, -2, 3, iso(2), 1, "c", "engine oil change")
    conn.commit()


def add_watch(conn, **kw):
    import json
    body = {"name": "k8s", "terms": ["kubernetes"], "exclude_terms": [],
            "chat_ids": [], "enabled": True}
    body.update(kw)
    conn.execute(
        "INSERT INTO watchlists (name, terms, exclude_terms, chat_ids, "
        "enabled, created_at) VALUES (?,?,?,?,?,datetime('now'))",
        (body["name"], json.dumps(body["terms"]),
         json.dumps(body["exclude_terms"]), json.dumps(body["chat_ids"]),
         1 if body["enabled"] else 0))
    conn.commit()


def test_matching_and_watermark(conn):
    seed(conn)
    add_watch(conn)
    stats = watchlists.evaluate_new(conn)
    assert stats["new_messages"] == 3
    assert stats["matches"] == 2          # both kubernetes messages

    # second run: nothing new -> no duplicates, no extra matches
    stats = watchlists.evaluate_new(conn)
    assert stats["new_messages"] == 0
    assert stats["matches"] == 0
    n = conn.execute("SELECT COUNT(*) c FROM alerts").fetchone()["c"]
    assert n == 2, "UNIQUE constraint prevents duplicate alerts"

    # a genuinely new message triggers exactly one new alert
    db.upsert_message(conn, -1, 10, iso(1), 1, "d", "kubernetes upgrade notes")
    conn.commit()
    stats = watchlists.evaluate_new(conn)
    assert stats["matches"] == 1


def test_exclusions_and_group_scope(conn):
    seed(conn)
    add_watch(conn, exclude_terms=["pricing"])
    stats = watchlists.evaluate_new(conn)
    texts = [r["msg_id"] for r in conn.execute(
        "SELECT msg_id FROM alerts").fetchall()]
    assert 2 not in texts, "excluded term suppresses the match"

    # scoped to the Cars group only -> no kubernetes hits there
    conn.execute("DELETE FROM alerts")
    conn.execute("DELETE FROM watchlists")
    conn.execute("DELETE FROM watch_watermarks")
    conn.commit()
    add_watch(conn, name="cars", terms=["engine"], chat_ids=[-2])
    stats = watchlists.evaluate_new(conn)
    assert stats["matches"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM alerts").fetchone()["c"] == 1


def test_arabic_terms_match_normalized_text(conn):
    seed(conn, with_msgs=False)
    db.upsert_message(conn, -1, 1, iso(1), 1, "a",
                      "شلووون أسعار السيارات الجديدة؟")
    conn.commit()
    add_watch(conn, name="car prices", terms=["كيف أسعار"])  # dialect + form
    stats = watchlists.evaluate_new(conn)
    assert stats["matches"] == 1, "terms normalize like search does"


def test_watchlists_never_call_ai(conn):
    """The spec's hard rule: watchlists work with NO provider configured."""
    import config
    old = config.settings.ai_api_key
    config.settings.ai_api_key = ""
    try:
        seed(conn)
        add_watch(conn)
        stats = watchlists.evaluate_new(conn)
        assert stats["matches"] == 2
    finally:
        config.settings.ai_api_key = old


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def test_watchlists_api(api_client):
    seed(api_client and db.get_db())
    r = api_client.post("/api/watchlists", json={
        "name": "k8s", "terms": ["kubernetes", "k8s"],
        "exclude_terms": [], "chat_ids": [], "enabled": True})
    assert r.status_code == 200
    wid = r.json()["id"]

    lst = api_client.get("/api/watchlists").json()
    assert lst[0]["terms"] == ["kubernetes", "k8s"]
    assert lst[0]["unread"] == 0

    # check now (no backfill needed - watermark starts at 0)
    r = api_client.post("/api/watchlists/check", json={"backfill_days": 0})
    assert r.json()["matches"] == 2
    assert r.json()["unread"] == 2

    # alerts inbox
    alerts = api_client.get("/api/alerts?state=new").json()
    assert len(alerts) == 2
    a = alerts[0]
    assert a["watchlist_name"] == "k8s"
    assert a["tg_link"]  # verified deep links on alerts too

    # read + archive
    r = api_client.post(f"/api/alerts/{a['id']}", json={"action": "read"})
    assert r.json()["unread"] == 1
    assert len(api_client.get("/api/alerts?state=new").json()) == 1
    api_client.post(f"/api/alerts/{a['id']}", json={"action": "archive"})
    assert len(api_client.get("/api/alerts?state=archived").json()) == 1

    # delete watchlist cascades its alerts
    api_client.delete(f"/api/watchlists/{wid}")
    assert api_client.get("/api/watchlists").json() == []
    with db.get_db() as conn:
        assert conn.execute("SELECT COUNT(*) c FROM alerts"
                            ).fetchone()["c"] == 0


def test_check_now_backfill_window(api_client):
    with db.get_db() as conn:
        seed(conn)
    api_client.post("/api/watchlists", json={
        "name": "k8s", "terms": ["kubernetes"], "chat_ids": []})
    # first check: everything is "new" (watermark 0)
    assert api_client.post("/api/watchlists/check",
                           json={"backfill_days": 0}).json()["matches"] == 2
    # pretend a later message arrived
    with db.get_db() as conn:
        db.upsert_message(conn, -1, 5, iso(0), 1, "z",
                          "kubernetes again and again")
        conn.commit()
    assert api_client.post("/api/watchlists/check",
                           json={"backfill_days": 0}).json()["matches"] == 1
