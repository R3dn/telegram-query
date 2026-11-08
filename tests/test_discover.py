"""Discovery engine tests (v0.7): term analytics, trending, stories,
activity, the unanswered-questions radar, and the topic timeline."""
import json
from datetime import datetime, timedelta, timezone

import pytest

import ai_tasks
import db
import discover


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
def _reset_calls():
    FakeClient.calls = []
    yield


# ---------------------------------------------------------------------------
# Term analytics
# ---------------------------------------------------------------------------

def test_message_terms_filters_stopwords_and_builds_bigrams():
    # elongation/dialect folding already live in text_norm - terms inherit it
    text_norm = db.normalize_text("thanks شكرا الجزيره الخضراء huge sale")
    terms = discover.message_terms(text_norm)
    assert "thanks" not in terms and "شكرا" not in terms
    assert "sale" in terms and "huge sale" in terms
    assert "الجزيره" in terms


def test_build_terms_incremental_and_watermarked(conn):
    db.upsert_chat(conn, -1, "G", "g", "group")
    db.upsert_message(conn, -1, 1, iso(1), 1, "a", "trail conditions muddy")
    db.upsert_message(conn, -1, 2, iso(1), 1, "a", "trail conditions great")
    conn.commit()
    s1 = discover.build_terms(conn)
    assert s1["messages"] == 2
    n = conn.execute("SELECT SUM(n) s FROM term_daily WHERE term='trail'"
                     ).fetchone()["s"]
    assert n == 2
    assert conn.execute(
        "SELECT 1 FROM term_daily WHERE term='trail conditions'").fetchone()
    # no new messages -> nothing reprocessed (watermark)
    s2 = discover.build_terms(conn)
    assert s2["messages"] == 0
    # new message -> only that one counted
    db.upsert_message(conn, -1, 3, iso(0), 2, "b", "trail report below")
    conn.commit()
    s3 = discover.build_terms(conn)
    assert s3["messages"] == 1


def test_trending_burst_vs_baseline(conn):
    db.upsert_chat(conn, -1, "G", "g", "group")
    # "solar" bursts now; "weather" is constant background
    for i in range(6):
        db.upsert_message(conn, -1, 100 + i, iso(1), 1, "a", "solar panel deal")
    for d in (20, 15, 10, 5, 2, 1):
        db.upsert_message(conn, -1, 200 + d, iso(d), 1, "a", "weather update")
    db.upsert_message(conn, -1, 300, iso(25), 1, "a", "weather check in")
    conn.commit()
    discover.build_terms(conn)
    rows = discover.trending(conn, days=7)
    terms = [r["term"] for r in rows]
    assert "solar" in terms
    solar = next(r for r in rows if r["term"] == "solar")
    weather = next(r for r in rows if r["term"] == "weather")
    assert solar["score"] > weather["score"]      # burst beats background
    assert solar["recent"] == 6 and solar["chats"] == 1
    assert solar["sample"] and solar["sample"]["chat_id"] == -1
    # volume sort ranks by absolute messages instead (weather: 7 > solar: 6)
    vrows = discover.trending(conn, days=30, sort="volume")
    assert vrows[0]["term"] == "weather"


def test_trending_min_volume_hides_rare_terms(conn):
    db.upsert_chat(conn, -1, "G", None, "group")
    db.upsert_message(conn, -1, 1, iso(0), 1, "a", "rare zanzibar event")
    conn.commit()
    discover.build_terms(conn)
    assert discover.trending(conn, days=7, min_volume=3) == []


# ---------------------------------------------------------------------------
# Cross-group stories
# ---------------------------------------------------------------------------

def test_story_detected_across_groups_and_noise_skipped(conn):
    db.upsert_chat(conn, -1, "A", "a", "group")
    db.upsert_chat(conn, -2, "B", None, "group")
    same = ("Community meetup Saturday 7pm at the central park pavilion, "
            "everyone welcome, bring snacks and drinks")
    db.upsert_message(conn, -1, 1, iso(1), 1, "a", same)
    db.upsert_message(conn, -2, 1, iso(1), 2, "b", same)
    # same-chat repeat is NOT a story; all-stopword chatter is not either
    db.upsert_message(conn, -1, 2, iso(1), 1, "a", same)
    db.upsert_message(conn, -2, 2, iso(0), 2, "b", "شكرا جزيلا على المعلومات القيمة")
    conn.commit()
    out = discover.stories(conn, days=7)
    assert len(out) == 1
    s = out[0]
    assert s["chats"] == 2 and s["n"] == 3   # the same-chat repeat counts too
    assert len(s["occurrences"]) == 3
    assert {o["chat_id"] for o in s["occurrences"]} == {-1, -2}
    assert s["sample_text"] == same
    # group scope filter respected
    assert discover.stories(conn, days=7, chat_ids=[-1]) == []


# ---------------------------------------------------------------------------
# Group activity (aggregate only)
# ---------------------------------------------------------------------------

def test_activity_aggregates_without_member_stats(conn):
    db.upsert_chat(conn, -1, "A", "a", "group")
    db.upsert_chat(conn, -2, "B", None, "channel")
    db.upsert_message(conn, -1, 1, iso(0), 1, "a", "hello there friends")
    db.upsert_message(conn, -1, 2, iso(0), 1, "b", "media post", has_media=1)
    db.upsert_message(conn, -2, 1, iso(0), 2, "c", "channel blast")
    db.upsert_message(conn, -2, 2, iso(0), 2, "c", "untracked world")
    conn.execute("UPDATE chats SET tracked=0 WHERE chat_id=-2")
    conn.commit()
    r = discover.activity(conn, days=30)
    assert r["totals"]["messages"] == 2 and r["totals"]["active_groups"] == 1
    g = r["groups"][0]
    assert g["chat_id"] == -1 and g["total"] == 2 and g["media"] == 1
    assert g["media_share"] == 0.5
    assert r["hours"] and 0 <= r["hours"][0]["hour"] <= 23
    # the response must never contain sender-level analytics
    assert "sender" not in json.dumps(r)


# ---------------------------------------------------------------------------
# Unanswered-questions radar
# ---------------------------------------------------------------------------

def _seed_questions(conn):
    db.upsert_chat(conn, -1, "Q", "qgroup", "group")
    # unanswered question
    db.upsert_message(conn, -1, 10, iso(1), 1, "sara",
                      "What shutter speed do you use for birds in flight?")
    # question answered by a reply (captured via reply_to)
    db.upsert_message(conn, -1, 11, iso(1), 2, "dave",
                      "How do I season a cast iron pan?")
    db.upsert_message(conn, -1, 12, iso(1), 3, "maya",
                      "Just use oil and heat it slowly for twenty minutes",
                      reply_to=11)
    # non-question noise
    db.upsert_message(conn, -1, 13, iso(1), 4, "omar", "nice shot today")
    conn.commit()


def test_radar_tracks_unanswered_and_skips_answered(conn):
    _seed_questions(conn)
    stats = discover.scan_questions(conn)
    assert stats["questions"] == 2
    assert stats["new_open"] == 1        # only the unanswered one is tracked
    rows = discover.question_list(conn)
    assert len(rows) == 1
    q = rows[0]
    assert q["msg_id"] == 10 and q["status"] == "open"
    assert q["tg_link"] == "https://t.me/qgroup/10"
    assert q["faq"] is None


def test_radar_auto_answers_when_a_reply_arrives_later(conn):
    _seed_questions(conn)
    discover.scan_questions(conn)
    # a reply arrives in a later sync
    db.upsert_message(conn, -1, 20, iso(0), 5, "pete",
                      "Use 1/2000s and burst mode, works every time",
                      reply_to=10)
    conn.commit()
    stats = discover.scan_questions(conn)
    assert stats["auto_answered"] == 1
    open_rows = discover.question_list(conn, status="open")
    assert open_rows == []
    answered = discover.question_list(conn, status="answered")
    assert answered[0]["answered_by"] == 20
    # a QUESTION reply is a follow-up question, not an answer
    assert discover.faq_suggestion(conn, "random words here") is None


def test_question_reply_that_is_a_question_does_not_answer(conn):
    db.upsert_chat(conn, -1, "Q", None, "group")
    db.upsert_message(conn, -1, 10, iso(1), 1, "a",
                      "How do I season a cast iron pan?")
    db.upsert_message(conn, -1, 11, iso(1), 2, "b",
                      "wait is seasoning really necessary?", reply_to=10)
    conn.commit()
    discover.scan_questions(conn)
    rows = discover.question_list(conn)
    assert len(rows) == 1 and rows[0]["status"] == "open"


def test_human_status_survives_rescans(conn):
    _seed_questions(conn)
    discover.scan_questions(conn)
    discover.set_question_status(conn, -1, 10, "ignored")
    # window rescan must not resurrect or duplicate the ignored question
    discover.scan_questions(conn, days=30)
    assert discover.question_list(conn, status="open") == []
    ig = discover.question_list(conn, status="ignored")
    assert len(ig) == 1
    assert discover.set_question_status(conn, -1, 10, "open") == 1


def test_faq_suggestion_links_approved_answer(conn):
    db.upsert_chat(conn, -1, "Q", None, "group")
    db.upsert_message(conn, -1, 10, iso(1), 1, "a",
                      "What shutter speed for birds in flight?")
    conn.commit()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO faq_clusters (question, norm_key, answer_md, status,
             frequency, first_seen, last_seen, source_questions,
             source_answers, updated_at)
           VALUES ('What shutter speed for birds?', 'birds flight shutter speed',
                   'Use 1/2000s [1]', 'approved', 3, ?, ?, '[]', '[]', ?)""",
        (now, now, now))
    conn.commit()
    discover.scan_questions(conn)
    rows = discover.question_list(conn)
    assert rows[0]["faq"] and rows[0]["faq"]["id"] == 1
    assert "1/2000s" in rows[0]["faq"]["answer_md"]


# ---------------------------------------------------------------------------
# Topic timeline (AI - mocked)
# ---------------------------------------------------------------------------

def test_topic_timeline_cites_validated_sources(conn, monkeypatch):
    db.upsert_chat(conn, -1, "G", "gg", "group")
    for i, (days, text) in enumerate([
            (10, "solar inverter v1 released"),
            (5, "solar inverter v2 firmware fixes the bug"),
            (1, "solar inverter price dropped to 199 SAR")]):
        db.upsert_message(conn, -1, 100 + i, iso(days), 1, "a", text)
    conn.commit()
    fake = FakeClient([json.dumps({
        "timeline_md": "## 2026-10-29 - v1 launched [1]\n\n"
                       "## 2026-11-07 - price drop [3] and a bogus [9]"
    })])
    monkeypatch.setattr(ai_tasks, "_get_client", lambda: fake)
    r = discover.topic_timeline(conn, "solar inverter")
    assert r["term"] == "solar inverter"
    assert "[9]" not in r["timeline_md"] and "[3]" in r["timeline_md"]
    assert len(r["sources"]) == 3
    assert r["sources"][0]["tg_link"] == "https://t.me/gg/100"
    assert FakeClient.calls[0]["model"]  # routed model recorded


def test_topic_timeline_needs_enough_messages(conn):
    db.upsert_chat(conn, -1, "G", None, "group")
    db.upsert_message(conn, -1, 1, iso(1), 1, "a", "only one zanzibar note")
    conn.commit()
    with pytest.raises(ValueError, match="at least 3"):
        discover.topic_timeline(conn, "zanzibar")


def test_rebuild_rebuilds_terms_and_questions(conn):
    _seed_questions(conn)
    discover.build_terms(conn)
    conn.execute("DELETE FROM term_daily")
    conn.execute("DELETE FROM open_questions")
    conn.commit()
    r = discover.rebuild(conn, verbose=lambda *_: None)
    assert r["terms"]["messages"] >= 4
    n = conn.execute("SELECT COUNT(*) c FROM term_daily").fetchone()["c"]
    assert n > 0
    assert discover.question_list(conn)  # radar recovered the open question


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------

def test_discover_api_endpoints(api_client):
    conn = db.get_db()
    try:
        db.upsert_chat(conn, -1, "ApiG", "apig", "group")
        db.upsert_chat(conn, -2, "ApiH", None, "group")
        same = ("Community meetup Saturday 7pm at the central park pavilion, "
                "everyone welcome, bring snacks and drinks")
        db.upsert_message(conn, -1, 1, iso(1), 1, "a", same)
        db.upsert_message(conn, -2, 1, iso(1), 1, "a", same)
        db.upsert_message(conn, -1, 2, iso(1), 2, "b",
                          "What shutter speed do you use for birds in flight?")
        conn.commit()
        discover.rebuild(conn, verbose=lambda *_: None)
    finally:
        conn.close()

    r = api_client.get("/api/discover/trending?days=7&min_volume=1")
    assert r.status_code == 200 and isinstance(r.json(), list)
    assert r.json() and r.json()[0]["term"]

    r = api_client.get("/api/discover/stories?days=7")
    assert r.status_code == 200 and len(r.json()) >= 1
    assert {o["chat_id"] for o in r.json()[0]["occurrences"]} == {-1, -2}

    r = api_client.get("/api/discover/activity?days=30")
    assert r.status_code == 200
    assert r.json()["totals"]["messages"] >= 3

    r = api_client.get("/api/discover/questions")
    assert r.status_code == 200 and len(r.json()) == 1
    q = r.json()[0]
    assert q["status"] == "open" and q["msg_id"] == 2

    r = api_client.post("/api/discover/questions/-1/2",
                        json={"status": "answered"})
    assert r.status_code == 200 and r.json()["status"] == "answered"
    r = api_client.get("/api/discover/questions")
    assert r.json() == []

    r = api_client.post("/api/discover/questions/scan", json={"days": 30})
    assert r.status_code == 200 and r.json()["ok"] is True
    # human statuses are never overwritten by a rescan
    assert api_client.get("/api/discover/questions").json() == []

    r = api_client.post("/api/discover/questions/-1/999",
                        json={"status": "open"})
    assert r.status_code == 404

    r = api_client.post("/api/discover/questions/-1/2",
                        json={"status": "bogus"})
    assert r.status_code == 422 or r.status_code == 400
