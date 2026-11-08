"""Entity gazetteer tests (v0.7): seeding, deterministic matching, merge,
ignore, watermark increments, and optional LLM discovery."""
import json
from datetime import datetime, timedelta, timezone

import pytest

import ai_tasks
import config
import db
import entities


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


@pytest.fixture(autouse=True)
def _reset(conn):
    FakeClient.calls = []
    conn.execute("DELETE FROM app_settings WHERE key LIKE 'entities%'")
    conn.commit()
    yield
    conn.execute("DELETE FROM app_settings WHERE key LIKE 'entities%'")
    conn.commit()


def _seed(conn, with_media=False):
    db.upsert_chat(conn, -1, "Deals", "dealz", "group")
    db.upsert_chat(conn, -2, "Tech", None, "group")
    db.upsert_message(conn, -1, 1, iso(1), 1, "ali",
                      "GadgetHub has a new laptop sleeve offer")
    db.upsert_message(conn, -2, 2, iso(1), 2, "sara",
                      "GadgetHub shipping was fast, love GadgetHub")
    db.upsert_message(conn, -1, 3, iso(0), 3, "omar",
                      "زاز كافيه فتح فرع جديد")           # arabic entity
    conn.commit()


# ---------------------------------------------------------------------------
# Gazetteer maintenance
# ---------------------------------------------------------------------------

def test_add_entity_normalizes_and_absorbs_duplicates(conn):
    a = entities.add_entity(conn, "GadgetHub", kind="brand",
                             verbose=lambda *_: None)
    assert a["norm_name"] == "gadgethub"
    # same normalized name -> merge as alias, never a duplicate row
    b = entities.add_entity(conn, "GADGET HUB", kind="brand",
                            aliases=["GadgetHub Store"],
                            verbose=lambda *_: None)
    assert b["id"] == a["id"]
    aliases = entities.list_entities(conn)[0]["aliases"]
    assert "gadget hub" in aliases and "gadgethub store" in aliases
    assert len(entities.list_entities(conn)) == 1


def test_add_entity_rejects_too_short_names(conn):
    with pytest.raises(ValueError, match="at least"):
        entities.add_entity(conn, "ok", verbose=lambda *_: None)


def test_seed_from_deals(conn):
    now = datetime.now(timezone.utc).isoformat()
    for vendor in ("GadgetHub", "Bean & Brew"):
        conn.execute(
            """INSERT INTO deals (title, vendor, fingerprint, first_seen,
                 last_seen, updated_at, status)
               VALUES (?, ?, ?, ?, ?, ?, 'unknown')""",
            (f"{vendor} offer", vendor, vendor.lower(), now, now, now))
    conn.commit()
    n = entities.seed_from_deals(conn, verbose=lambda *_: None)
    assert n == 2
    names = {e["name"] for e in entities.list_entities(conn)}
    assert names == {"GadgetHub", "Bean & Brew"}


def test_update_entity_rename_conflict_and_ignore(conn):
    a = entities.add_entity(conn, "Alpha", verbose=lambda *_: None)
    entities.add_entity(conn, "Beta", verbose=lambda *_: None)
    with pytest.raises(ValueError, match="merge"):
        entities.update_entity(conn, a["id"], name="Beta")
    updated = entities.update_entity(conn, a["id"], ignored=True)
    assert updated["ignored"] == 1
    visible = entities.list_entities(conn)
    assert len(visible) == 1 and visible[0]["name"] == "Beta"


# ---------------------------------------------------------------------------
# Deterministic matching
# ---------------------------------------------------------------------------

def test_matching_links_mentions_and_respects_ignore(conn):
    _seed(conn)
    entities.add_entity(conn, "GadgetHub", kind="brand",
                        verbose=lambda *_: None)
    stats = entities.match_and_discover(conn, verbose=lambda *_: None)
    assert stats["new_messages"] == 3
    # msg 1 + msg 2 (one mention row per message, never per occurrence)
    assert stats["mentions"] == 2
    row = entities.entity_detail(conn, 1)
    assert row["mentions_count"] == 2
    assert {m["chat_id"] for m in row["mentions"]} == {-1, -2}
    assert row["groups"] and len(row["groups"]) == 2
    assert row["daily"]  # 30-day series for the sparkline
    # ignoring hides the entity and stops future matching; the history
    # stays inspectable through the detail endpoint
    entities.update_entity(conn, 1, ignored=True)
    detail = entities.entity_detail(conn, 1)
    assert detail["mentions_count"] == 2


def test_matching_is_incremental(conn):
    _seed(conn)
    entities.add_entity(conn, "GadgetHub", verbose=lambda *_: None)
    entities.match_and_discover(conn, verbose=lambda *_: None)
    # new message arrives in a later sync
    db.upsert_message(conn, -1, 10, iso(0), 4, "nora",
                      "GadgetHub restocked the sleeves")
    conn.commit()
    stats = entities.match_and_discover(conn, verbose=lambda *_: None)
    assert stats["new_messages"] == 1 and stats["mentions"] == 1
    # nothing new -> nothing processed (watermark)
    stats = entities.match_and_discover(conn, verbose=lambda *_: None)
    assert stats["new_messages"] == 0


def test_alias_and_multiword_matching(conn):
    db.upsert_chat(conn, -1, "G", None, "group")
    db.upsert_message(conn, -1, 1, iso(0), 1, "a",
                      "the aurora coffee roastery opened downtown")
    conn.commit()
    entities.add_entity(conn, "Aurora Coffee", kind="brand",
                        aliases=["Aurora Roastery"],
                        verbose=lambda *_: None)
    stats = entities.match_and_discover(conn, verbose=lambda *_: None)
    assert stats["mentions"] == 1     # multiword name matched as substring
    detail = entities.entity_detail(conn, 1)
    assert detail["mentions"][0]["msg_id"] == 1


def test_rebuild_rematches_everything(conn):
    _seed(conn)
    entities.add_entity(conn, "GadgetHub", verbose=lambda *_: None)
    entities.rebuild(conn, verbose=lambda *_: None)
    marks = json.loads(db.get_setting(conn, "entities_watermark", "{}"))
    assert marks == {"-1": 3, "-2": 2}
    stats = entities.match_and_discover(conn, verbose=lambda *_: None)
    assert stats["new_messages"] == 0   # watermark covers everything


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def test_merge_moves_mentions_and_aliases(conn):
    _seed(conn)
    a = entities.add_entity(conn, "GadgetHub", verbose=lambda *_: None)
    b = entities.add_entity(conn, "gadget hub store", verbose=lambda *_: None)
    entities.match_and_discover(conn, verbose=lambda *_: None)
    merged = entities.merge_entities(conn, b["id"], a["id"])
    assert merged["merged"]["mentions_moved"] >= 0
    assert conn.execute("SELECT COUNT(*) c FROM entities WHERE id=?",
                        (b["id"],)).fetchone()["c"] == 0
    detail = entities.entity_detail(conn, a["id"])
    assert "gadget hub store" in detail["aliases"]
    assert detail["mentions_count"] == 2     # all mentions under one entity
    with pytest.raises(ValueError, match="itself"):
        entities.merge_entities(conn, a["id"], a["id"])


# ---------------------------------------------------------------------------
# Optional LLM discovery (extraction model, opt-in, cached)
# ---------------------------------------------------------------------------

def test_llm_discovery_opt_in_adds_and_matches_in_one_run(conn, monkeypatch):
    _seed(conn)
    fake = FakeClient([json.dumps({"entities": [
        {"name": "زاز كافيه", "kind": "brand"},
    ]})])
    monkeypatch.setattr(ai_tasks, "_get_client", lambda: fake)
    db.set_setting(conn, "entities_auto", "1")
    stats = entities.match_and_discover(conn, verbose=lambda *_: None)
    assert stats["new_entities"] == 1
    names = {e["name"] for e in entities.list_entities(conn)}
    assert names == {"زاز كافيه"}
    assert stats["mentions"] == 1          # arabic mention matched immediately
    assert FakeClient.calls[0]["model"] == config.settings.model_for("extract")


def test_llm_discovery_invalid_payload_gets_one_repair(conn, monkeypatch):
    _seed(conn)
    # first reply violates the schema (empty name); the second is valid
    fake = FakeClient([
        json.dumps({"entities": [{"name": "", "kind": "other"}]}),
        json.dumps({"entities": [{"name": "GadgetHub", "kind": "brand"}]}),
    ])
    monkeypatch.setattr(ai_tasks, "_get_client", lambda: fake)
    db.set_setting(conn, "entities_auto", "1")
    stats = entities.match_and_discover(conn, verbose=lambda *_: None)
    assert stats["new_entities"] == 1
    assert len(FakeClient.calls) == 2     # exactly one repair attempt
    # persistently-invalid output is discarded honestly, never guessed
    fake2 = FakeClient([json.dumps({"entities": [{"name": ""}]})] * 2)
    monkeypatch.setattr(ai_tasks, "_get_client", lambda: fake2)
    conn.execute("DELETE FROM entities")
    conn.execute("DELETE FROM ai_task_cache")
    conn.execute("DELETE FROM app_settings WHERE key LIKE 'entities_watermark'")
    db.set_setting(conn, "entities_auto", "1")
    conn.commit()
    stats = entities.match_and_discover(conn, verbose=lambda *_: None)
    assert stats["new_entities"] == 0


def test_llm_discovery_skipped_when_not_opted_in(conn, monkeypatch):
    _seed(conn)
    fake = FakeClient([json.dumps({"entities": []})])
    monkeypatch.setattr(ai_tasks, "_get_client", lambda: fake)
    stats = entities.match_and_discover(conn, verbose=lambda *_: None)
    assert stats["new_entities"] == 0
    assert FakeClient.calls == []           # no provider call at all


def test_llm_discovery_failure_degrades_to_gazetteer_only(conn, monkeypatch):
    _seed(conn)
    entities.add_entity(conn, "GadgetHub", verbose=lambda *_: None)

    def boom():
        raise ai_tasks.TaskError("provider down")

    class ExplodingChat:
        completions = boom

    class ExplodingClient:
        chat = ExplodingChat()

    monkeypatch.setattr(ai_tasks, "_get_client", lambda: ExplodingClient())
    db.set_setting(conn, "entities_auto", "1")
    stats = entities.match_and_discover(conn, verbose=lambda *_: None)
    assert stats["mentions"] == 2          # deterministic matching unaffected
    assert stats["new_entities"] == 0


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------

def test_entities_api(api_client):
    r = api_client.get("/api/discover/entities/settings")
    assert r.status_code == 200 and r.json()["auto"] is False

    r = api_client.post("/api/discover/entities",
                        json={"name": "GadgetHub", "kind": "brand"})
    assert r.status_code == 200 and r.json()["id"]

    conn = db.get_db()
    try:
        db.upsert_chat(conn, -1, "ApiG", "apig", "group")
        db.upsert_message(conn, -1, 1, iso(1), 1, "a",
                          "GadgetHub sale now on")
        conn.commit()
        entities.match_and_discover(conn, verbose=lambda *_: None)
    finally:
        conn.close()

    eid = api_client.get("/api/discover/entities").json()[0]["id"]
    r = api_client.get(f"/api/discover/entities/{eid}")
    assert r.status_code == 200
    assert r.json()["mentions_count"] == 1
    assert r.json()["mentions"][0]["tg_link"] == "https://t.me/apig/1"

    r = api_client.patch(f"/api/discover/entities/{eid}",
                         json={"ignored": True})
    assert r.status_code == 200 and r.json()["ignored"] == 1
    assert api_client.get("/api/discover/entities").json() == []

    r = api_client.post("/api/discover/entities", json={"name": "ok"})
    assert r.status_code == 400

    # merge via API: a second entity folded into the first
    r = api_client.post("/api/discover/entities", json={"name": "Other Brand"})
    other = r.json()["id"]
    r = api_client.post("/api/discover/entities/merge",
                        json={"source_id": other, "target_id": eid})
    assert r.status_code == 200
    assert api_client.get(f"/api/discover/entities/{other}").status_code == 404

    r = api_client.delete(f"/api/discover/entities/{eid}")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert api_client.get(f"/api/discover/entities/{eid}").status_code == 404
