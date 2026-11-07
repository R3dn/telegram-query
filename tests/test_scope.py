"""AI scope chips tests: explicit scope must restrict retrieval for real."""
import json
from datetime import datetime, timedelta, timezone

import ai
import db


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.chat = type("Chat", (), {"completions": self})()
        self._calls = []

    def create(self, model=None, messages=None, temperature=None):
        self._calls.append(messages)
        text = self.responses.pop(0)

        class Msg:
            class _C:
                content = None
            message = _C()
        class Resp:
            choices = [Msg()]
        Resp.choices[0].message.content = text
        return Resp


def spec(kws):
    return json.dumps({"keywords": kws, "chat_titles": [],
                       "date_from": None, "date_to": None,
                       "relative_days": None})


def iso(days_ago, hour=10):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)
            ).replace(hour=hour).isoformat()


def seed(conn):
    db.upsert_chat(conn, -1, "Deals", None, "group")
    db.upsert_chat(conn, -2, "Cars", None, "group")
    for i in range(1, 6):
        db.upsert_message(conn, -1, i, iso(i), 1, "s",
                          "pizza deal with a discount code")
    for i in range(1, 4):
        db.upsert_message(conn, -2, i, iso(i), 1, "c",
                          "pizza deal for car service")


def test_scope_restricts_groups(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([spec(["pizza deal"]), "Answer [1]."])
    monkeypatch.setattr(ai, "get_client", lambda: fake)

    r = ai.ask(conn, "pizza deals?", scope={"chat_ids": [-2]})
    assert r["answer"].startswith("Answer")
    assert r["sources"], "expected sources"
    assert all(s["chat_id"] == -2 for s in r["sources"]), \
        "explicit scope must override the LLM's own group guesses"


def test_scope_date_range(conn, monkeypatch):
    seed(conn)
    # enough day-1 hits that the pipeline stops after the first attempt
    for i in (100, 101, 102):
        db.upsert_message(conn, -1, i, iso(1), 1, "s",
                           "pizza deal fresh today")
    fake = FakeClient([spec(["pizza deal"]), "Answer [1]."])
    monkeypatch.setattr(ai, "get_client", lambda: fake)

    day = iso(1)[:10]
    r = ai.ask(conn, "pizza deals?", scope={"date_from": day, "date_to": day})
    assert r["sources"], "expected scoped hits"
    assert all(s["date"][:10] == day for s in r["sources"]), \
        "explicit date scope must restrict retrieval to that day"


def test_scope_echoed_in_result(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([spec(["pizza"]), "Answer [1]."])
    monkeypatch.setattr(ai, "get_client", lambda: fake)
    r = ai.ask(conn, "pizza?", scope={"chat_ids": [-1], "date_from": "2020-01-01"})
    assert r["scope"]["chat_ids"] == [-1]
    assert r["scope"]["date_from"] == "2020-01-01"


def test_no_scope_uses_all_groups(conn, monkeypatch):
    """No chips selected -> behaves exactly like v0.3 (LLM decides)."""
    seed(conn)
    fake = FakeClient([spec(["pizza deal"]), "Answer [1]."])
    monkeypatch.setattr(ai, "get_client", lambda: fake)
    r = ai.ask(conn, "pizza deals?")
    assert {s["chat_id"] for s in r["sources"]} == {-1, -2}


def test_api_accepts_scope(api_client, monkeypatch):
    seed_db = db.get_db()
    try:
        seed(seed_db)
    finally:
        seed_db.close()

    import api.ai as ai_api
    captured = {}

    def fake_ask_db(question, scope=None):
        captured["scope"] = scope
        return {"answer": "ok [1]", "sources": [
            {"chat_id": -1, "msg_id": 1, "chat_title": "Deals",
             "date": iso(1), "sender_name": "s", "text": "pizza",
             "has_media": 0}],
            "attempts": 1, "keywords_tried": [["pizza"]],
            "fallback": None,
            "scope": {"chat_ids": scope.get("chat_ids", []) if scope else [],
                      "date_from": scope.get("date_from") if scope else None,
                      "date_to": scope.get("date_to") if scope else None}}

    monkeypatch.setattr(ai_api.ai, "ask_db", fake_ask_db)
    r = api_client.post("/api/ask", json={
        "question": "pizza?",
        "scope": {"chat_ids": [-1], "date_from": "2026-01-01"}})
    assert r.status_code == 200
    assert captured["scope"]["chat_ids"] == [-1]
    assert r.json()["scope"]["chat_ids"] == [-1]
