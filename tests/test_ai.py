"""AI pipeline tests with a mocked OpenAI-compatible client (no network)."""
import json
from datetime import datetime, timedelta, timezone

import ai
import db


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)

    def create(self, model=None, messages=None, temperature=None):
        # record calls for assertions
        FakeCompletions.calls.append({"model": model, "messages": messages})
        text = self.responses.pop(0)

        class Msg:
            class _C:  # noqa: N801
                content = None
            message = _C()
        class Resp:
            choices = [Msg()]
        Resp.choices[0].message.content = text
        return Resp

FakeCompletions.calls = []


class FakeClient:
    def __init__(self, responses):
        self.chat = type("Chat", (), {"completions": FakeCompletions(responses)})()


def extract_spec(kws, chat_titles=None, days=None):
    return json.dumps({
        "keywords": kws,
        "chat_titles": chat_titles or [],
        "date_from": None,
        "date_to": None,
        "relative_days": days,
    })


def iso(days_ago, hour=10):
    """ISO date for a message *days_ago* (keeps recent-fallback tests valid)."""
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)
            ).replace(hour=hour).isoformat()


def seed(conn):
    db.upsert_chat(conn, -1, "Deals", None, "group")
    db.upsert_chat(conn, -2, "Cars", None, "group")
    for i in range(1, 6):
        db.upsert_message(conn, -1, i, iso(i % 3), 1, f"s{i}",
                          f"pizza deal code P{i}")
    for i in range(1, 4):
        db.upsert_message(conn, -2, i, iso(i), 1, "c",
                          "engine oil change discussion")


def test_ask_happy_path(conn, monkeypatch):
    seed(conn)
    responses = [
        extract_spec(["pizza deal"]),                            # extraction
        "Here are the pizza deals [1] with codes [2].",          # answer
    ]
    fake = FakeClient(responses)
    monkeypatch.setattr(ai, "get_client", lambda: fake)

    r = ai.ask(conn, "What pizza deals exist?")
    assert r["answer"].startswith("Here are the pizza deals")
    assert r["sources"], "expected grounded sources"
    assert all(s["chat_title"] == "Deals" for s in r["sources"])
    assert r["attempts"] == 1
    # settings-driven model passed to the fake client
    assert FakeCompletions.calls[0]["model"] == "test-model"


def test_ask_retries_with_new_keywords(conn, monkeypatch):
    seed(conn)
    # first keywords match nothing; retry keywords match
    responses = [
        extract_spec(["nothing-matches-this"]),
        extract_spec(["pizza deal"]),
        "Answer after retry [1].",
    ]
    fake = FakeClient(responses)
    monkeypatch.setattr(ai, "get_client", lambda: fake)

    r = ai.ask(conn, "pizza deals?")
    assert r["attempts"] == 2
    assert len(r["keywords_tried"]) == 2
    assert r["sources"]


def test_ask_falls_back_to_recent(conn, monkeypatch):
    seed(conn)
    responses = [
        extract_spec(["zzz-no-match"]),
        extract_spec(["zzz-still-nothing"]),
        extract_spec(["zzz-again-nothing"]),
        "Recent-only answer [1].",
    ]
    fake = FakeClient(responses)
    monkeypatch.setattr(ai, "get_client", lambda: fake)

    r = ai.ask(conn, "what happened lately?")
    assert r["fallback"] == "recent"
    assert r["sources"]  # recent messages are the sources


def test_ask_diverse_retrieval(conn, monkeypatch):
    """No explicit chat filter -> hits from BOTH tracked chats."""
    seed(conn)
    for i in range(6, 30):
        db.upsert_message(conn, -2, i, iso(1), 1, "c",
                          "engine oil change discussion")
    responses = [
        extract_spec(["pizza", "oil"]),   # pizza->Deals, oil->Cars
        "Mixed answer [1].",
    ]
    fake = FakeClient(responses)
    monkeypatch.setattr(ai, "get_client", lambda: fake)

    r = ai.ask(conn, "discussions?")
    chats = {s["chat_title"] for s in r["sources"]}
    assert chats == {"Deals", "Cars"}


def test_not_configured(monkeypatch, conn):
    import config
    monkeypatch.setattr(config.settings, "ai_api_key", "")
    r = ai.ask(conn, "anything")
    assert r["answer"] is None and r["error"]
    assert r["sources"] == []


def test_parse_json_tolerates_code_fences():
    assert ai._parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert ai._parse_json('{"a": 1}') == {"a": 1}
    assert ai._parse_json("not json at all") is None
