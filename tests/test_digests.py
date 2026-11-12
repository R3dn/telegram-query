"""Digests tests: generation, citation validation, reuse, schedules, API."""
import json
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

import config
import db
import digests


def iso(days_ago, hour=10):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)
            ).replace(hour=hour).isoformat()


class FakeClient:
    calls = []

    def __init__(self, responses):
        self.responses = list(responses)
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, model=None, messages=None, temperature=None):
        FakeClient.calls.append(messages)
        text = self.responses.pop(0)

        class Resp:
            class _Msg:
                class _M:
                    content = None
                message = _M()
            choices = [_Msg()]
        Resp.choices[0].message.content = text
        return Resp


def digest_md(text):
    return json.dumps({"digest_md": text})


def seed(conn, n=6):
    db.upsert_chat(conn, -1, "Tech talk", "techtalk", "group")
    db.upsert_chat(conn, -2, "Cars", None, "group")
    for i in range(1, n + 1):
        db.upsert_message(conn, -1, i, iso(i % 2), 1, f"u{i}",
                          f"kubernetes migration update number {i}")
    db.upsert_message(conn, -1, n + 1, iso(1), 1, "v",
                      "بلاغ هام عن الصيانة المجانية غدا")
    conn.commit()


@pytest.fixture(autouse=True)
def _reset():
    FakeClient.calls = []
    yield


def test_generate_validates_and_saves(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([digest_md(
        "## Top discussions\nThe migration rolled out [1] and costs dropped [3].\n"
        "A fake claim [77] must vanish.")])
    monkeypatch.setattr("ai.get_client", lambda: fake)

    r = digests.generate(conn, chat_ids=[-1])
    assert r["reused"] is False
    row = conn.execute("SELECT * FROM digests WHERE id=?", (r["id"],)).fetchone()
    assert "[77]" not in row["content_md"]
    assert "backend note" in row["content_md"]
    cites = conn.execute(
        "SELECT COUNT(*) c FROM digest_citations WHERE digest_id=?",
        (r["id"],)).fetchone()["c"]
    assert cites == 2
    assert row["prompt_version"] == digests.PROMPT_VERSION


def test_unchanged_period_is_never_repaid(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([digest_md("## Top discussions\nMigration news [1] with details [2] here.")])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    r1 = digests.generate(conn, chat_ids=[-1])
    r2 = digests.generate(conn, chat_ids=[-1])
    assert r1["reused"] is False and r2["reused"] is True
    assert len(FakeClient.calls) == 1, "identical period+content is cached"
    assert conn.execute("SELECT COUNT(*) c FROM digests").fetchone()["c"] == 1


def test_empty_period_is_an_honest_error(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    with pytest.raises(ValueError):
        digests.generate(conn, chat_ids=[-2], period_start="2020-01-01",
                         period_end="2020-01-02")
    assert conn.execute("SELECT COUNT(*) c FROM digests").fetchone()["c"] == 0


def test_language_auto_detects_arabic(conn, monkeypatch):
    db.upsert_chat(conn, -1, "Tech talk", "techtalk", "group")
    for i in range(1, 5):
        db.upsert_message(conn, -1, i, iso(1), 1, "u",
                          "صيانة مجانية لجميع العملاء الجدد هذا الأسبوع")
    conn.commit()
    fake = FakeClient([digest_md("## أهم النقاشات\nعرض الصيانة المجانية سارٍ [1].")])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    digests.generate(conn, chat_ids=[-1])
    # the language instruction reached the provider
    assert any("Arabic" in (m[0]["content"] if isinstance(m, list) else m[0])
               for m in FakeClient.calls)


def test_due_schedules_logic(conn):
    now = datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc)
    # daily due (never run, hour passed)
    conn.execute(
        "INSERT INTO digest_schedules (frequency, chat_ids, hour, weekday, "
        "language, enabled, created_at, last_run) "
        "VALUES ('daily','[]',9,6,'auto',1,'t',NULL)")
    # daily NOT due: ran today already
    conn.execute(
        "INSERT INTO digest_schedules (frequency, chat_ids, hour, weekday, "
        "language, enabled, created_at, last_run) "
        "VALUES ('daily','[]',9,6,'auto',1,'t',?)",
        (now.isoformat(),))
    # weekly due on Saturday (weekday 5)
    conn.execute(
        "INSERT INTO digest_schedules (frequency, chat_ids, hour, weekday, "
        "language, enabled, created_at, last_run) "
        "VALUES ('weekly','[]',9,5,'auto',1,'t',NULL)")
    # weekly not due: wrong weekday (Nov 7 2026 is a Saturday = weekday 5)
    conn.execute(
        "INSERT INTO digest_schedules (frequency, chat_ids, hour, weekday, "
        "language, enabled, created_at, last_run) "
        "VALUES ('weekly','[]',9,1,'auto',1,'t',NULL)")
    conn.commit()
    due = digests.due_schedules(conn, now=now)
    kinds = sorted(s["frequency"] for s in due)
    assert kinds == ["daily", "weekly"], "due = hour passed + not run today"


def test_digests_api(api_client, monkeypatch):
    with closing(db.get_db()) as conn:
        seed(conn)
    fake = FakeClient([digest_md("## Top discussions\nMigration update [1] and more [2] to report.")])
    monkeypatch.setattr("ai.get_client", lambda: fake)

    r = api_client.post("/api/digests/schedules", json={
        "frequency": "daily", "chat_ids": [-1], "hour": 9,
        "language": "auto", "enabled": True})
    assert r.status_code == 200
    sid = r.json()["id"]
    assert len(api_client.get("/api/digests/schedules").json()) == 1

    # on-demand generation runs the real pipeline (mocked provider)
    with closing(db.get_db()) as conn:
        result = digests.generate(conn, chat_ids=[-1], schedule_id=sid)
    did = result["id"]

    lst = api_client.get("/api/digests").json()
    assert len(lst) == 1
    d = api_client.get(f"/api/digests/{did}").json()
    assert "citations" in d and len(d["citations"]) == 2
    assert any("t.me/techtalk/" in (c.get("tg_link") or "")
               for c in d["citations"])

    assert api_client.delete(f"/api/digests/{did}").json()["ok"] is True
    assert api_client.get(f"/api/digests/{did}").status_code == 404


def test_generate_requires_ai(api_client, monkeypatch):
    monkeypatch.setattr(config.settings, "ai_api_key", "")
    r = api_client.post("/api/digests/generate", json={})
    assert r.status_code == 400
