"""FAQ discovery tests: clustering, human gate, review flags, API."""
import json
from datetime import datetime, timedelta, timezone

import db
import faq


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


def answer_md(text):
    return json.dumps({"answer_md": text})


def seed(conn):
    db.upsert_chat(conn, -1, "Tech talk", "techtalk", "group")
    # the SAME question asked twice (slightly different wording, same intent)
    db.upsert_message(conn, -1, 1, iso(5), 1, "a", "how do i backup my database?")
    db.upsert_message(conn, -1, 2, iso(4), 1, "b", "How to backup the database?")
    db.upsert_message(conn, -1, 3, iso(4), 1, "c", "use pg_dump nightly", reply_to=2)
    # a DIFFERENT question asked once (must not merge with the backup one)
    db.upsert_message(conn, -1, 4, iso(3), 1, "d", "what is the best hosting provider?")
    db.upsert_message(conn, -1, 5, iso(3), 1, "e", "i use digitalocean", reply_to=4)
    # not questions at all
    db.upsert_message(conn, -1, 6, iso(2), 1, "f", "the migration finished today")
    conn.commit()


def test_clustering_and_gate(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([
        answer_md("Run pg_dump nightly as shown in the replies [3]."),
        # the second cluster (hosting) is asked once -> NO answer drafted
    ])
    monkeypatch.setattr("ai.get_client", lambda: fake)

    faq.discover(conn)
    rows = conn.execute(
        "SELECT * FROM faq_clusters ORDER BY frequency DESC").fetchall()
    # two clusters: backup question (freq 2) and hosting question (freq 1)
    assert len(rows) == 2
    backup = rows[0]
    assert backup["frequency"] == 2
    assert backup["status"] == "candidate", "human approval is required"
    assert "pg_dump" in (backup["answer_md"] or "")
    # single-occurrence question got NO provider call (never answered)
    assert len(FakeClient.calls) == 1
    hosting = rows[1]
    assert hosting["frequency"] == 1 and hosting["answer_md"] is None


def test_new_evidence_flags_approved_for_review(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([answer_md("Run pg_dump nightly as shown in the replies [3].")])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    faq.discover(conn)
    row = conn.execute("SELECT * FROM faq_clusters WHERE frequency=2"
                       ).fetchone()
    # human approves
    conn.execute("UPDATE faq_clusters SET status='approved' WHERE id=?",
                 (row["id"],))
    conn.commit()

    # the question is asked again later -> approved answers are NOT
    # silently replaced; the cluster is flagged for re-review
    db.upsert_message(conn, -1, 20, iso(0), 1, "g",
                      "how should i backup my database now?")
    conn.commit()
    faq.discover(conn, days=7)
    row2 = conn.execute("SELECT * FROM faq_clusters WHERE id=?",
                        (row["id"],)).fetchone()
    assert row2["status"] == "needs_review"
    assert "pg_dump" in row2["answer_md"], "the approved text stays intact"


def test_unrelated_questions_do_not_merge(conn, monkeypatch):
    seed(conn)
    faq.discover(conn, days=30)   # provider never called for the freq<2 clusters
    # re-seed: make two DIFFERENT recurring questions that share a word
    db.upsert_chat(conn, -3, "S", None, "group")
    for i, (mid, q) in enumerate([
            (1, "what is the best oil for my car engine?"),
            (2, "what is the best oil for cooking?")], start=100):
        db.upsert_message(conn, -3, mid, iso(i % 2), 1, "u", q)
        db.upsert_message(conn, -3, mid + 1, iso(i % 2), 1, "u", q + " any tips")
    conn.commit()
    faq.discover(conn, chat_ids=[-3], days=30)
    rows = conn.execute(
        "SELECT question, frequency FROM faq_clusters").fetchall()
    assert len(rows) >= 2, "different topics stay different clusters"


def test_discover_covers_the_newest_end_of_a_busy_window(conn):
    """v1.0.2 regression: the 1000-message window read used to start at
    the OLDEST end of the scope, so on a busy archive the newest
    questions (the point of the feature) were silently never scanned."""
    db.upsert_chat(conn, -1, "Busy", "busy", "group")
    # 1100 old non-question messages ...
    for i in range(1, 1101):
        db.upsert_message(conn, -1, i, iso(80), 1, "s", f"status update {i}")
    # ... and the recurring question only in the NEWEST part of the window
    db.upsert_message(conn, -1, 2001, iso(2), 1, "a",
                      "how do i backup my database?")
    db.upsert_message(conn, -1, 2002, iso(1), 1, "b",
                      "how to backup the database?")
    conn.commit()

    faq.discover(conn, days=90)
    rows = conn.execute(
        "SELECT frequency FROM faq_clusters WHERE frequency >= 2").fetchall()
    assert rows, ("the newest-window recurring question must be found even "
                  "when the window holds more than the 1000-message cap")


def test_faqs_api_flow(api_client, monkeypatch):
    with db.get_db() as conn:
        seed(conn)
    fake = FakeClient([answer_md("Run pg_dump nightly as shown in the replies [3].")])
    monkeypatch.setattr("ai.get_client", lambda: fake)

    queued = []

    def fake_start(name, func, front=False):
        queued.append(name)
        return True

    monkeypatch.setattr("api.faqs.jobs.JOBS.start", fake_start)
    r = api_client.post("/api/faqs/discover", json={"chat_ids": [-1], "days": 30})
    assert r.status_code == 200 and r.json()["started"] is True
    assert queued == ["faq"]
    # run the pipeline synchronously (the job is intercepted above)
    with db.get_db() as conn:
        faq.discover(conn, chat_ids=[-1], days=30)

    lst = api_client.get("/api/faqs?status=candidate").json()
    assert len(lst) >= 1
    f = lst[0]
    assert f["source_questions"][0]["tg_link"], "sources carry deep links"
    assert "pg_dump" in f["answer_md"]

    # approve -> it leaves the candidate queue
    r = api_client.patch(f"/api/faqs/{f['id']}", json={"status": "approved"})
    assert r.json()["status"] == "approved"
    assert len(api_client.get("/api/faqs?status=approved").json()) == 1

    # reject every other cluster (e.g. the once-asked hosting question)
    for o in api_client.get("/api/faqs").json():
        if o["id"] != f["id"]:
            api_client.patch(f"/api/faqs/{o['id']}",
                             json={"status": "rejected"})
    assert api_client.get("/api/faqs?status=candidate").json() == []
    assert len(api_client.get("/api/faqs?status=rejected").json()) == 1

    # edit the approved answer (human correction)
    r = api_client.patch(f"/api/faqs/{f['id']}",
                         json={"answer_md": "استخدم pg_dump كل ليلة"})
    assert "pg_dump" in r.json()["answer_md"]
    assert api_client.delete(f"/api/faqs/{f['id']}").json()["ok"] is True
