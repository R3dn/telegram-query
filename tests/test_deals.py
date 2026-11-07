"""Deals extractor tests: pipeline, validation, dedupe, status, API."""
import json
from datetime import datetime, timedelta, timezone

import pytest

import config
import db
import deals


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
    # the same offer forwarded in both chats (must merge, sources preserved)
    offer_ar = "عرض خاص على البيتزا خصم 40% بكود SAVE40 ينتهي 2030-01-01"
    offer_en = "AWS credits worth $500 available for startups - promo code"
    db.upsert_message(conn, -1, 1, iso(2), 1, "ali", offer_ar)
    db.upsert_message(conn, -2, 1, iso(2), 2, "sara", offer_ar)  # forwarded copy
    db.upsert_message(conn, -1, 2, iso(1), 1, "omar", offer_en)
    # noise: a price discussion (the model should NOT extract it)
    db.upsert_message(conn, -2, 2, iso(1), 3, "nora", "شلون أسعار البيتزا؟")
    for i in range(3, 3 + n_extra_noise):
        db.upsert_message(conn, -2, i, iso(1), 3, "nora", "engine oil change")
    conn.commit()


def extraction(deals_list):
    return json.dumps({"deals": deals_list})


@pytest.fixture(autouse=True)
def _reset_calls():
    FakeClient.calls = []
    yield


def test_extract_stores_and_merges(conn, monkeypatch):
    seed(conn)
    # two offers: the AR one is also posted (forwarded) in the second chat.
    # Extraction refers to lead indexes 1 and 2 (order = bm25 rank).
    fake = FakeClient([extraction([
        {
            "title": "بيتزا خصم 40%", "description": "عرض بيتزا", "category": "food",
            "vendor": "Pizza", "discount_pct": 40, "price": None, "currency": "SAR",
            "promo_code": "SAVE40", "eligibility": None, "geo": None,
            "valid_from": None, "expires": "2030-01-01", "status": "active",
            "confidence": 0.9, "source_indexes": [1],
        },
        {
            "title": "AWS startup credits", "description": None,
            "category": "cloud", "vendor": "AWS", "discount_pct": None,
            "price": 500, "currency": "USD", "promo_code": None,
            "eligibility": "startups", "geo": None, "valid_from": None,
            "expires": None, "status": "unknown",
            "confidence": 0.7, "source_indexes": [2],
        },
    ])])
    monkeypatch.setattr("ai.get_client", lambda: fake)

    stats = deals.extract(conn)
    assert stats["new_deals"] == 2
    rows = conn.execute(
        "SELECT d.* FROM deals d").fetchall()
    assert len(rows) == 2
    by_code = {r["promo_code"]: dict(r) for r in rows}
    assert set(by_code) == {"SAVE40", None}
    # the forwarded copy joined the deal whose message it reposted, so
    # exactly one deal carries 2 sources across BOTH chats
    src_counts = {}
    src_chats = {}
    for d in rows:
        src = conn.execute(
            "SELECT chat_id, msg_id FROM deal_sources WHERE deal_id=?",
            (d["id"],)).fetchall()
        src_counts[d["id"]] = len(src)
        src_chats[d["id"]] = {s["chat_id"] for s in src}
    assert sorted(src_counts.values()) == [1, 2]
    merged_id = next(i for i, n in src_counts.items() if n == 2)
    assert len(src_chats[merged_id]) == 2, "cross-group repost keeps both sources"
    # model status kept separate from derived status
    pizza = by_code["SAVE40"]
    assert pizza["status"] == "active"
    assert deals.derived_status(pizza) == "active"


def test_invalid_extraction_discarded(conn, monkeypatch):
    """A deal whose citation does not resolve to a real message is dropped -
    the model can never invent message references."""
    seed(conn)
    fake = FakeClient([extraction([
        {"title": "ghost deal", "source_indexes": [99], "status": "unknown",
         "confidence": 0.5},              # index out of range -> skipped
        {"title": "real deal", "source_indexes": [1], "status": "unknown",
         "confidence": 0.5},              # valid -> stored
    ])])
    monkeypatch.setattr("ai.get_client", lambda: fake)

    stats = deals.extract(conn)
    assert stats["new_deals"] == 1
    assert stats["skipped_invalid"] == 1
    # the ghost left no trace
    rows = conn.execute("SELECT title FROM deals").fetchall()
    assert [r["title"] for r in rows] == ["real deal"]


def test_malformed_twice_never_fabricates(conn, monkeypatch):
    seed(conn)
    fake = FakeClient(["not json at all", "still not json"])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    with pytest.raises(deals.ai_tasks.TaskError):
        deals.extract(conn)
    assert conn.execute("SELECT COUNT(*) c FROM deals").fetchone()["c"] == 0


def test_repair_attempt_recovers(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([
        "{broken json",  # invalid -> one repair
        extraction([{"title": "بيتزا خصم 40%", "source_indexes": [1],
                     "status": "active", "confidence": 0.9,
                     "expires": "2030-01-01"}]),
    ])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    stats = deals.extract(conn)
    assert stats["new_deals"] == 1
    assert len(FakeClient.calls) == 2   # first + repair


def test_batch_cache_prevents_resending(conn, monkeypatch):
    """Identical sources -> cache hit, no second provider call."""
    seed(conn)
    good = extraction([{"title": "بيتزا خصم 40%", "source_indexes": [1],
                        "status": "active", "confidence": 0.9,
                        "expires": "2030-01-01"}])
    fake = FakeClient([good])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    deals.extract(conn)
    deals.extract(conn)          # same scope, same content
    assert len(FakeClient.calls) == 1, "unchanged sources must not be re-sent"
    # and the merge kept it one deal
    assert conn.execute("SELECT COUNT(*) c FROM deals").fetchone()["c"] == 1


def test_incremental_watermark(conn, monkeypatch):
    seed(conn)
    fake = FakeClient([extraction([])])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    watermark = {str(cid): 1000 for cid in (-1, -2)}
    db.set_setting(conn, "deals_watermark", json.dumps(watermark))
    conn.commit()

    stats = deals.extract(conn, incremental=True)
    # everything is below the watermark -> no candidates, no provider calls
    assert stats["candidates"] == 0
    assert len(FakeClient.calls) == 0


def test_derived_status_matrix():
    assert deals.derived_status(
        {"status": "active", "expires": "2020-01-01"}) == "expired"
    assert deals.derived_status(
        {"status": "active", "valid_from": "2100-01-01"}) == "upcoming"
    assert deals.derived_status(
        {"status": "active", "expires": "2100-01-01"}) == "active"
    assert deals.derived_status(
        {"status": "active"}) == "unverified", "no evidence -> never active"
    assert deals.derived_status({"status": "unknown"}) == "unknown"
    assert deals.confidence_label(0.9) == "high"
    assert deals.confidence_label(0.5) == "medium"
    assert deals.confidence_label(None) == "low"


# ---------------------------------------------------------------------------
# API layer
# ---------------------------------------------------------------------------

def test_deals_api_crud(api_client, monkeypatch):
    with db.get_db() as conn:
        seed(conn)
    fake = FakeClient([extraction([
        {"title": "بيتزا خصم 40%", "source_indexes": [1], "status": "active",
         "confidence": 0.9, "expires": "2030-01-01", "promo_code": "SAVE40",
         "vendor": "Pizza", "category": "food"},
    ])])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    with db.get_db() as conn:
        deals.extract(conn)

    r = api_client.get("/api/deals")
    rows = r.json()
    assert len(rows) == 1
    d = rows[0]
    assert d["promo_code"] == "SAVE40"
    assert d["derived_status"] == "active"
    # every source carries its verified Telegram link when one exists
    assert any(s.get("tg_link") and "t.me/dealz/" in s["tg_link"]
               for s in d["sources"])

    # dismiss hides it from the default list
    r = api_client.patch(f"/api/deals/{d['id']}",
                         json={"user_status": "dismissed"})
    assert r.json()["user_status"] == "dismissed"
    assert api_client.get("/api/deals").json() == []
    # explicit status filter still reaches it
    assert len(api_client.get("/api/deals?status=dismissed").json()) == 1

    # manual add: unverified + human-confirmed, requires a real source
    r = api_client.post("/api/deals", json={
        "title": "مكتبة تقنية خصم 20%", "promo_code": "BOOK20",
        "chat_id": -1, "msg_id": 1})
    assert r.status_code == 200
    manual = r.json()
    assert manual["status"] == "unverified"
    assert manual["user_status"] == "confirmed"
    assert manual["human_added"] is True
    assert len(manual["sources"]) == 1

    assert api_client.delete(f"/api/deals/{manual['id']}").json()["ok"] is True
    assert api_client.delete(f"/api/deals/{manual['id']}").status_code == 404


def test_extract_requires_ai(api_client, monkeypatch):
    monkeypatch.setattr(config.settings, "ai_api_key", "")
    r = api_client.post("/api/deals/extract", json={})
    assert r.status_code == 400
    assert "AI is not configured" in r.json()["error"]


def test_deals_auto_toggle(api_client):
    r = api_client.get("/api/deals/settings")
    assert r.json()["auto"] is False
    assert api_client.post("/api/deals/auto", json={"enabled": True}).json()["auto"] is True
    with db.get_db() as conn:
        assert db.get_setting(conn, "deals_auto") == "1"
    api_client.post("/api/deals/auto", json={"enabled": False})
    with db.get_db() as conn:
        assert db.get_setting(conn, "deals_auto") == "0"


def test_deals_export(api_client, monkeypatch):
    with db.get_db() as conn:
        seed(conn)
    fake = FakeClient([extraction([
        {"title": "عرض بيتزا", "source_indexes": [1], "status": "active",
         "confidence": 0.9, "expires": "2030-01-01", "promo_code": "SAVE40"},
    ])])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    with db.get_db() as conn:
        deals.extract(conn)

    r = api_client.get("/api/export/deals?format=json")
    data = r.json()
    assert data["count"] == 1
    assert data["deals"][0]["promo_code"] == "SAVE40"
    assert any("t.me/dealz/" in (s.get("tg_link") or "")
               for s in data["deals"][0]["sources"])

    r = api_client.get("/api/export/deals")
    body = r.content.decode("utf-8")
    assert "SAVE40" in body
    assert "t.me/dealz/" in body  # verified source links survive export
