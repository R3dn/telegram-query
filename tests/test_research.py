"""Research briefs tests: generation, citation validation, versions,
staleness, API."""
import json
from datetime import datetime, timedelta, timezone

import pytest

import ai_tasks
import db
import research


def iso(days_ago, hour=10):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)
            ).replace(hour=hour).isoformat()


class FakeClient:
    calls = []

    def __init__(self, responses):
        self.responses = list(responses)
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, model=None, messages=None, temperature=None):
        FakeClient.calls.append({"model": model, "messages": messages})
        text = self.responses.pop(0)

        class Resp:
            class _Msg:
                class _M:
                    content = None
                message = _M()
            choices = [_Msg()]
        Resp.choices[0].message.content = text
        return Resp


def keywords(kws):
    return json.dumps({"keywords": kws})


def brief_md(text):
    return json.dumps({"brief_md": text})


def seed(conn):
    db.upsert_chat(conn, -1, "Tech talk", "techtalk", "group")
    db.upsert_chat(conn, -2, "Cars", None, "group")
    for i in range(1, 9):
        db.upsert_message(conn, -1, i, iso(i), 1, f"u{i}",
                          f"kubernetes migration notes part {i}")
    # a reply thread (v0.5 reply_to capture)
    db.upsert_message(conn, -1, 9, iso(1), 1, "u9",
                      "here is the cluster yaml", reply_to=8)
    for i in range(1, 4):
        db.upsert_message(conn, -2, i, iso(i), 1, "c",
                          "engine oil change discussion")
    conn.commit()


@pytest.fixture(autouse=True)
def _reset():
    FakeClient.calls = []
    yield


def test_generate_validates_citations_and_saves_version(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([
        keywords(["kubernetes migration"]),
        brief_md("## Executive summary\nThe team moved to k8s [1]. "
                 "Costs dropped [3].\n\nA bogus claim [42] must vanish."),
    ])
    monkeypatch.setattr("ai.get_client", lambda: fake)

    brief_id = research.create_brief(conn, "Summarize the kubernetes migration")
    result = research.generate(conn, brief_id)

    assert result["version"] == 1
    assert result["invalid_removed"] == [42]
    ver = research.latest_version(conn, brief_id)
    assert "[42]" not in ver["answer_md"]
    assert "backend note" in ver["answer_md"], "unresolvable citations reported"

    cites = research.version_citations(conn, ver["id"])
    assert {c["idx"] for c in cites} == {1, 3}
    # every citation resolves to a real archived message with a link
    assert all(c["text"] is not None for c in cites)
    assert cites[0]["tg_link"] == "https://t.me/techtalk/1"


def test_regeneration_creates_new_version(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([keywords(["kubernetes"]),
                       brief_md("## Executive summary\nFirst-pass findings on the migration [1]."),
                       keywords(["kubernetes"]),
                       brief_md("## Executive summary\nSecond pass adds richer, deeper findings [1] [2].")])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    brief_id = research.create_brief(conn, "kubernetes migration?")

    research.generate(conn, brief_id)
    research.generate(conn, brief_id)

    vers = conn.execute(
        "SELECT version FROM brief_versions WHERE brief_id=? ORDER BY version",
        (brief_id,)).fetchall()
    assert [v["version"] for v in vers] == [1, 2], "history is preserved"


def test_reply_targets_join_the_context(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([
        keywords(["kubernetes migration", "cluster yaml"]),
        # the reply target (msg 8) is cited even though retrieval matched 9
        brief_md("## Findings\nThe full cluster yaml is archived at [8]; the reply thread confirms it at [9]."),
    ])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    brief_id = research.create_brief(conn, "where is the cluster yaml?")
    research.generate(conn, brief_id)
    ver = research.latest_version(conn, brief_id)
    cited_ids = {c["msg_id"] for c in research.version_citations(conn, ver["id"])}
    assert 8 in cited_ids, "context expansion must include reply targets"


def test_staleness_is_deterministic(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([keywords(["kubernetes migration"]),
                       brief_md("## Summary\nThe migration findings are recorded here [1] [2].")])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    brief_id = research.create_brief(conn, "kubernetes migration?")
    research.generate(conn, brief_id)
    assert research.staleness(conn, brief_id) == 0

    # new relevant messages appear AFTER the version
    db.upsert_message(conn, -1, 50,
                      datetime.now(timezone.utc).isoformat(), 1, "u",
                      "new kubernetes migration update today")
    conn.commit()
    n_calls = len(FakeClient.calls)
    assert research.staleness(conn, brief_id) >= 1
    assert len(FakeClient.calls) == n_calls, "staleness never calls the provider"


def test_too_few_sources_saves_nothing(conn, monkeypatch):
    seed(conn)
    # keywords that match nothing in scope -> honest error, no version
    fake = FakeClient([keywords(["zzz-no-match-xyz"])])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    brief_id = research.create_brief(conn, "what about gibberish topic?")
    with pytest.raises(ai_tasks.TaskError):
        research.generate(conn, brief_id)
    assert research.latest_version(conn, brief_id) is None


# ---------------------------------------------------------------------------
# API layer
# ---------------------------------------------------------------------------

def test_brief_api_flow(api_client, monkeypatch):
    with db.get_db() as conn:
        seed(conn)

    queued = []

    def fake_start(name, func, front=False):
        queued.append(name)
        return True

    monkeypatch.setattr("api.research.jobs.JOBS.start", fake_start)

    r = api_client.post("/api/briefs", json={
        "question": "Summarize the kubernetes migration",
        "chat_ids": [-1],
    })
    assert r.status_code == 200
    brief_id = r.json()["id"]
    assert queued == ["brief"]

    # generate synchronously through the real pipeline (mocked provider)
    fake = FakeClient([keywords(["kubernetes migration"]),
                       brief_md("## Summary\nThe kubernetes migration is summarized with evidence [1].")])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    with db.get_db() as conn:
        research.generate(conn, brief_id)

    r = api_client.get(f"/api/briefs/{brief_id}")
    d = r.json()
    assert d["latest"]["version"] == 1
    assert "kubernetes" in d["latest"]["answer_md"]
    assert d["latest"]["citations"][0]["chat_title"] == "Tech talk"
    assert d["stale_count"] == 0

    assert api_client.post(f"/api/briefs/{brief_id}/regenerate"
                           ).json()["queued"] is True

    lst = api_client.get("/api/briefs").json()
    assert lst[0]["latest_version"] == 1

    # patch: rename question + notes
    r = api_client.patch(f"/api/briefs/{brief_id}",
                         json={"notes": "my notes عن الموضوع"})
    assert r.json()["notes"].startswith("my notes")

    # export md with citations
    r = api_client.get(f"/api/export/briefs/{brief_id}")
    body = r.content.decode("utf-8")
    assert "kubernetes" in body
    assert "https://t.me/techtalk/" in body

    assert api_client.delete(f"/api/briefs/{brief_id}").json()["ok"] is True
    assert api_client.get(f"/api/briefs/{brief_id}").status_code == 404


def test_missing_brief_404(api_client):
    assert api_client.get("/api/briefs/999").status_code == 404
    assert api_client.delete("/api/briefs/999").status_code == 404
