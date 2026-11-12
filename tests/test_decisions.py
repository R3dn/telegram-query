"""Decisions extractor tests: pipeline, validation, dedupe, status, API."""
import json
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

import config
import db
import decisions


def iso(days_ago, hour=10):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)
            ).replace(hour=hour).isoformat()


class FakeClient:
    """OpenAI-compatible fake for ai_tasks (records every call)."""
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
            class _U:
                prompt_tokens = 10
                completion_tokens = 5
            choices = [_Msg()]
            usage = _U()
        Resp.choices[0].message.content = text
        return Resp


def seed(conn, n_extra_noise=5):
    db.upsert_chat(conn, -1, "Dealz", "dealz", "group")
    db.upsert_chat(conn, -2, "Tech talk", None, "group")
    # the same decision forwarded in both chats (must merge, sources kept)
    dec_ar = "اتفقنا إننا نبدأ تصميم الموقع الأسبوع القادم والمسؤول عنه أحمد"
    dec_en = "We decided to migrate the database to Postgres by Friday - owner: Sara"
    db.upsert_message(conn, -1, 1, iso(2), 1, "ali", dec_ar)
    db.upsert_message(conn, -2, 1, iso(2), 2, "sara", dec_ar)  # forwarded copy
    db.upsert_message(conn, -1, 2, iso(1), 1, "omar", dec_en)
    # noise: a question about options (the model should NOT extract it)
    db.upsert_message(conn, -2, 2, iso(1), 3, "nora", "نشوف وش نقرر بعدين؟")
    for i in range(3, 3 + n_extra_noise):
        db.upsert_message(conn, -2, i, iso(1), 3, "nora", "engine oil change")
    conn.commit()


def extraction(decisions_list):
    return json.dumps({"decisions": decisions_list})


@pytest.fixture(autouse=True)
def _reset_calls():
    FakeClient.calls = []
    yield


def test_extract_stores_and_merges(conn, monkeypatch):
    seed(conn)
    # two decisions: the AR one is also forwarded to the second chat.
    # Extraction refers to lead indexes 1 and 2 (order = bm25 rank).
    fake = FakeClient([extraction([
        {
            "title": "نبدأ تصميم الموقع الأسبوع القادم",
            "detail": "المسؤول أحمد", "kind": "commitment",
            "owner": "أحمد", "due_date": None,
            "status": "committed", "confidence": 0.9,
            "source_indexes": [1],
        },
        {
            "title": "Migrate database to Postgres",
            "detail": "deadline Friday", "kind": "decision",
            "owner": "Sara", "due_date": "2030-01-01",
            "status": "committed", "confidence": 0.8,
            "source_indexes": [2],
        },
    ])])
    monkeypatch.setattr("ai.get_client", lambda: fake)

    stats = decisions.extract(conn)
    assert stats["new_decisions"] == 2
    rows = conn.execute("SELECT d.* FROM decisions d").fetchall()
    assert len(rows) == 2
    by_owner = {r["owner"]: dict(r) for r in rows}
    assert set(by_owner) == {"أحمد", "Sara"}
    # the forwarded copy joined the record whose message it reposted, so
    # exactly one decision carries 2 sources across BOTH chats
    src_counts = {}
    src_chats = {}
    for d in rows:
        src = conn.execute(
            "SELECT chat_id, msg_id FROM decision_sources WHERE decision_id=?",
            (d["id"],)).fetchall()
        src_counts[d["id"]] = len(src)
        src_chats[d["id"]] = {s["chat_id"] for s in src}
    assert sorted(src_counts.values()) == [1, 2]
    merged_id = next(i for i, n in src_counts.items() if n == 2)
    assert len(src_chats[merged_id]) == 2, \
        "cross-group repost keeps both sources"
    # model status kept separate from derived status
    ar = by_owner["أحمد"]
    assert ar["status"] == "committed"
    assert decisions.derived_status(ar) == "committed"


def test_invalid_extraction_discarded(conn, monkeypatch):
    """A decision whose citation does not resolve to a real message is
    dropped - the model can never invent message references."""
    seed(conn)
    fake = FakeClient([extraction([
        {"title": "ghost decision", "source_indexes": [99],
         "status": "unknown", "confidence": 0.5},  # out of range -> skipped
        {"title": "real decision", "source_indexes": [1],
         "status": "unknown", "confidence": 0.5},  # valid -> stored
    ])])
    monkeypatch.setattr("ai.get_client", lambda: fake)

    stats = decisions.extract(conn)
    assert stats["new_decisions"] == 1
    assert stats["skipped_invalid"] == 1
    rows = conn.execute("SELECT title FROM decisions").fetchall()
    assert [r["title"] for r in rows] == ["real decision"]


def test_malformed_twice_never_fabricates(conn, monkeypatch):
    seed(conn)
    fake = FakeClient(["not json at all", "still not json"])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    with pytest.raises(decisions.ai_tasks.TaskError):
        decisions.extract(conn)
    assert conn.execute("SELECT COUNT(*) c FROM decisions"
                        ).fetchone()["c"] == 0


def test_repair_attempt_recovers(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([
        "{broken json",  # invalid -> one repair
        extraction([{"title": "نبدأ التصميم", "source_indexes": [1],
                     "status": "committed", "confidence": 0.9}]),
    ])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    stats = decisions.extract(conn)
    assert stats["new_decisions"] == 1
    assert len(FakeClient.calls) == 2   # first + repair


def test_batch_cache_prevents_resending(conn, monkeypatch):
    """Identical sources -> cache hit, no second provider call."""
    seed(conn)
    good = extraction([{"title": "نبدأ التصميم", "source_indexes": [1],
                        "status": "committed", "confidence": 0.9}])
    fake = FakeClient([good])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    decisions.extract(conn)
    decisions.extract(conn)     # same scope, same content
    assert len(FakeClient.calls) == 1, "unchanged sources must not be re-sent"
    assert conn.execute("SELECT COUNT(*) c FROM decisions"
                        ).fetchone()["c"] == 1


def test_incremental_watermark(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([extraction([])])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    watermark = {str(cid): 1000 for cid in (-1, -2)}
    db.set_setting(conn, "decisions_watermark", json.dumps(watermark))
    conn.commit()

    stats = decisions.extract(conn, incremental=True)
    # everything is below the watermark -> no candidates, no provider calls
    assert stats["candidates"] == 0
    assert len(FakeClient.calls) == 0


def test_derived_status_matrix():
    today = "2026-11-09"
    assert decisions.derived_status(
        {"status": "completed"}, today) == "completed"
    assert decisions.derived_status(
        {"status": "cancelled"}, today) == "cancelled"
    # past due date, not done -> overdue (evidence-derived)
    assert decisions.derived_status(
        {"status": "committed", "due_date": "2026-01-01"}, today) == "overdue"
    assert decisions.derived_status(
        {"status": "completed", "due_date": "2026-01-01"}, today) == "completed"
    # future due date does not flip anything by itself
    assert decisions.derived_status(
        {"status": "committed", "due_date": "2100-01-01"}, today) == "committed"
    assert decisions.derived_status(
        {"status": "proposed"}, today) == "proposed"
    assert decisions.derived_status(
        {"status": "unknown"}, today) == "unverified", \
        "no evidence -> never silently committed"
    assert decisions.confidence_label(0.9) == "high"
    assert decisions.confidence_label(0.5) == "medium"
    assert decisions.confidence_label(None) == "low"


# ---------------------------------------------------------------------------
# Follow-up tracking (v0.8.1) - deterministic, incremental
# ---------------------------------------------------------------------------

def _store_decision_direct(conn, title, chat_id, msg_id, status="committed"):
    """Insert one decision with a single citation (no AI involved)."""
    now = "2026-11-09T00:00:00+00:00"
    cur = conn.execute(
        """INSERT INTO decisions (title, detail, kind, status, confidence,
             fingerprint, prompt_version, model, first_seen, last_seen,
             updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (title, "", "commitment", status, 0.9,
         f"fp-{abs(hash(title)) % 10**8}", "test", "test-model",
         now, now, now))
    dec_id = cur.lastrowid
    conn.execute(
        "INSERT OR IGNORE INTO decision_sources (decision_id, chat_id, msg_id)"
        " VALUES (?,?,?)", (dec_id, chat_id, msg_id))
    conn.commit()
    return dec_id


def test_followups_found_and_incremental(conn):
    db.upsert_chat(conn, -1, "Dealz", "dealz", "group")
    # the decision (msg 1): "launch the new website design"
    db.upsert_message(conn, -1, 1, iso(3), 1, "ali",
                      "We decided to launch the new website design next week")
    # a newer message that discusses it (hits: launch, website, design)
    db.upsert_message(conn, -1, 2, iso(2), 2, "sara",
                      "about the website design launch - is the header ready?")
    # noise: only one keyword hit
    db.upsert_message(conn, -1, 3, iso(2), 3, "nora",
                      "check the design of my business card please")
    conn.commit()

    dec_id = _store_decision_direct(
        conn, "launch the new website design", -1, 1)
    stats = decisions.check_followups(conn)
    assert stats["decisions"] == 1
    assert stats["new_followups"] == 1, "two-keyword message is a follow-up"
    rows = conn.execute(
        "SELECT * FROM decision_followups WHERE decision_id=?",
        (dec_id,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["msg_id"] == 2
    assert json.loads(rows[0]["matched_terms"]), "matched terms are stored"

    # second run is a no-op: the watermark advanced past the follow-up
    stats = decisions.check_followups(conn)
    assert stats["new_followups"] == 0, "incremental - nothing re-found"


def test_followups_skip_closed_and_dismissed(conn):
    db.upsert_chat(conn, -1, "Dealz", "dealz", "group")
    db.upsert_message(conn, -1, 1, iso(3), 1, "ali",
                      "We decided to launch the new website design")
    db.upsert_message(conn, -1, 2, iso(2), 2, "sara",
                      "website design launch status update")
    conn.commit()
    _store_decision_direct(conn, "launch the new website design",
                           -1, 1, status="completed")
    gone = _store_decision_direct(conn, "launch the new website design v2",
                                  -1, 1, status="committed")
    conn.execute("UPDATE decisions SET user_status='dismissed' WHERE id=?",
                 (gone,))
    conn.commit()

    stats = decisions.check_followups(conn)
    assert stats["checked"] == 0, "completed + dismissed rows are not checked"
    assert conn.execute("SELECT COUNT(*) c FROM decision_followups"
                        ).fetchone()["c"] == 0


def test_followup_keywords_filter_stopwords():
    kws = decisions._followup_keywords(
        "We decided to launch the new website design")
    assert "the" not in kws and "to" not in kws
    assert "launch" in kws and "website" in kws and "design" in kws
    # arabic stopwords are filtered with the shared discovery pack
    kws_ar = decisions._followup_keywords("قررنا نبدأ تصميم الموقع الجديد")
    assert all(w not in ("من", "في", "على") for w in kws_ar)
    assert len(kws) <= decisions.FOLLOWUP_MAX_TERMS


# ---------------------------------------------------------------------------
# API layer
# ---------------------------------------------------------------------------

def test_decisions_api_crud(api_client, monkeypatch):
    with closing(db.get_db()) as conn:
        seed(conn)
    fake = FakeClient([extraction([
        {"title": "نبدأ تصميم الموقع", "source_indexes": [1],
         "status": "committed", "confidence": 0.9, "kind": "commitment",
         "owner": "أحمد"},
    ])])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    with closing(db.get_db()) as conn:
        decisions.extract(conn)

    r = api_client.get("/api/decisions")
    rows = r.json()
    assert len(rows) == 1
    d = rows[0]
    assert d["owner"] == "أحمد"
    assert d["derived_status"] == "committed"
    # every source carries its verified Telegram link when one exists
    assert any(s.get("tg_link") and "t.me/dealz/" in s["tg_link"]
               for s in d["sources"])

    # dismiss hides it from the default list
    r = api_client.patch(f"/api/decisions/{d['id']}",
                         json={"user_status": "dismissed"})
    assert r.json()["user_status"] == "dismissed"
    assert api_client.get("/api/decisions").json() == []
    # explicit status filter still reaches it
    assert len(api_client.get(
        "/api/decisions?status=dismissed").json()) == 1

    # manual add: committed + human-confirmed, requires a real source
    r = api_client.post("/api/decisions", json={
        "title": "متابعة الاجتماع يوم الأحد", "kind": "commitment",
        "owner": "عمر", "chat_id": -1, "msg_id": 1})
    assert r.status_code == 200
    manual = r.json()
    assert manual["status"] == "committed"
    assert manual["user_status"] == "confirmed"
    assert manual["human_added"] is True
    assert len(manual["sources"]) == 1

    # status correction (human marks it completed)
    r = api_client.patch(f"/api/decisions/{manual['id']}",
                         json={"status": "completed"})
    assert r.json()["derived_status"] == "completed"
    # invalid status rejected
    r = api_client.patch(f"/api/decisions/{manual['id']}",
                         json={"status": "bogus"})
    assert r.status_code == 400

    assert api_client.delete(
        f"/api/decisions/{manual['id']}").json()["ok"] is True
    assert api_client.delete(
        f"/api/decisions/{manual['id']}").status_code == 404


def test_extract_requires_ai(api_client, monkeypatch):
    monkeypatch.setattr(config.settings, "ai_api_key", "")
    r = api_client.post("/api/decisions/extract", json={})
    assert r.status_code == 400
    assert "AI is not configured" in r.json()["error"]


def test_followup_api_and_monitor(api_client, monkeypatch):
    with closing(db.get_db()) as conn:
        db.upsert_chat(conn, -1, "Dealz", "dealz", "group")
        db.upsert_message(conn, -1, 1, iso(3), 1, "ali",
                          "We decided to launch the new website design")
        db.upsert_message(conn, -1, 2, iso(2), 2, "sara",
                          "website design launch status update")
        db.upsert_message(conn, -1, 3, iso(1), 4, "omar",
                          "website design launch delayed one week")
        conn.commit()
        _store_decision_direct(conn, "launch the new website design", -1, 1)
        # an overdue decision for the monitor counts
        dec2 = _store_decision_direct(conn, "prepare the quarterly report",
                                      -1, 3)
        conn.execute("UPDATE decisions SET due_date='2020-01-01' WHERE id=?",
                     (dec2,))
        conn.commit()

    # manual check endpoint (also rides every sync via the post-sync hook)
    r = api_client.post("/api/decisions/check-followups")
    assert r.status_code == 200
    stats = r.json()
    assert stats["new_followups"] >= 1

    # rows carry the follow-ups + counts
    rows = api_client.get("/api/decisions").json()
    web = next(d for d in rows if "website" in d["title"])
    assert web["followup_count"] == 2
    assert len(web["followups"]) == 2
    assert all(f["tg_link"] for f in web["followups"])
    rep = next(d for d in rows if "quarterly" in d["title"])
    assert rep["derived_status"] == "overdue"
    assert rep["due_soon"] is False

    # monitor counts: overdue >= 1, with_followups >= 1
    mon = api_client.get("/api/decisions/monitor").json()
    assert mon["open"] == 2
    assert mon["overdue"] == 1
    assert mon["with_followups"] == 1


def test_export_decisions(api_client, monkeypatch):
    with closing(db.get_db()) as conn:
        seed(conn)
    fake = FakeClient([extraction([
        {"title": "نبدأ تصميم الموقع", "source_indexes": [1],
         "status": "committed", "confidence": 0.9, "kind": "commitment",
         "owner": "أحمد"},
    ])])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    with closing(db.get_db()) as conn:
        decisions.extract(conn)

    r = api_client.get("/api/export/decisions?format=md")
    assert r.status_code == 200
    assert "نبدأ تصميم الموقع" in r.text
    assert "owner: أحمد" in r.text
    r = api_client.get("/api/export/decisions?format=json")
    data = r.json()
    assert data["count"] == 1
    assert data["decisions"][0]["sources"], "exports keep citations"
