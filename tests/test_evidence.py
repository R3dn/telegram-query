"""Evidence Explorer tests: the unified reverse-citation lookup."""
import json
from datetime import datetime, timedelta, timezone

import db


def iso(days_ago, hour=10):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)
            ).replace(hour=hour).isoformat()


def seed_all_kinds(conn):
    """One message referenced by every citation table."""
    db.upsert_chat(conn, -1, "Dealz", "dealz", "group")
    db.upsert_message(conn, -1, 1, iso(2), 1, "ali",
                      "offer pizza discount code SAVE40")
    db.upsert_message(conn, -1, 2, iso(1), 2, "sara",
                      "reply about the pizza offer")  # plain reply row
    conn.commit()
    now = "2026-11-09T00:00:00+00:00"

    # deal citing msg 1
    deal_id = conn.execute(
        """INSERT INTO deals (title, status, expires, confidence, fingerprint,
             prompt_version, model, first_seen, last_seen, updated_at)
           VALUES ('Pizza 40% off', 'active', '2030-01-01', 0.9, 'fp-deal',
                   'test', 'm', ?, ?, ?)""", (now, now, now)).lastrowid
    conn.execute(
        "INSERT INTO deal_sources (deal_id, chat_id, msg_id) "
        "VALUES (?,?,1)", (deal_id, -1))

    # decision citing msg 1 + a follow-up row pointing at msg 2
    dec_id = conn.execute(
        """INSERT INTO decisions (title, kind, status, confidence,
             fingerprint, prompt_version, model, first_seen, last_seen,
             updated_at)
           VALUES ('order pizza for the party', 'commitment', 'committed',
                   0.9, 'fp-dec', 'test', 'm', ?, ?, ?)""",
        (now, now, now)).lastrowid
    conn.execute(
        "INSERT INTO decision_sources (decision_id, chat_id, msg_id) "
        "VALUES (?,?,1)", (dec_id, -1))
    conn.execute(
        """INSERT INTO decision_followups (decision_id, chat_id, msg_id,
             matched_terms, created_at)
           VALUES (?,?,2,'["pizza","offer"]',?)""",
        (dec_id, -1, now))

    # brief version citing msg 1
    brief_id = conn.execute(
        "INSERT INTO briefs (question, chat_ids, created_at, updated_at) "
        "VALUES ('what offers?', '[-1]', ?, ?)", (now, now)).lastrowid
    version_id = conn.execute(
        """INSERT INTO brief_versions (brief_id, version, answer_md,
             prompt_version, model, created_at)
           VALUES (?, 1, 'answer', 'test', 'm', ?)""",
        (brief_id, now)).lastrowid
    conn.execute(
        "INSERT INTO brief_citations (version_id, idx, chat_id, msg_id, excerpt)"
        " VALUES (?, 0, -1, 1, 'offer pizza')", (version_id,))

    # digest citing msg 1
    digest_id = conn.execute(
        """INSERT INTO digests (period_start, period_end, content_md,
             prompt_version, model, fingerprint, created_at)
           VALUES ('2026-11-01', '2026-11-08', 'md', 'test', 'm', 'fp',
                   ?)""", (now,)).lastrowid
    conn.execute(
        "INSERT INTO digest_citations (digest_id, idx, chat_id, msg_id, excerpt)"
        " VALUES (?, 0, -1, 1, 'offer pizza')", (digest_id,))

    # alert on msg 1
    wl_id = conn.execute(
        "INSERT INTO watchlists (name, terms, created_at) "
        "VALUES ('pizza', '[\"pizza\"]', ?)", (now,)).lastrowid
    conn.execute(
        """INSERT INTO alerts (watchlist_id, chat_id, msg_id, matched_term,
             created_at) VALUES (?,?,1, 'pizza', ?)""", (wl_id, -1, now))

    # faq cluster with msg 1 as a source question
    conn.execute(
        """INSERT INTO faq_clusters (question, norm_key, frequency,
             first_seen, last_seen, updated_at, source_questions)
           VALUES ('any pizza offers?', 'normkey', 3, ?, ?, ?, ?)""",
        (now, now, now,
         json.dumps([{"chat_id": -1, "msg_id": 1, "date": now}])))

    # entity mentioning msg 1
    ent_id = conn.execute(
        """INSERT INTO entities (name, norm_name, kind, created_at,
             updated_at) VALUES ('Pizza Hut', 'pizza hut', 'brand', ?, ?)""",
        (now, now)).lastrowid
    conn.execute(
        "INSERT INTO entity_mentions (entity_id, chat_id, msg_id, date) "
        "VALUES (?,?,1, ?)", (ent_id, -1, now))
    conn.commit()


def test_evidence_unifies_all_citations(api_client):
    with db.get_db() as conn:
        seed_all_kinds(conn)

    r = api_client.get("/api/evidence", params={"chat_id": -1, "msg_id": 1})
    assert r.status_code == 200
    data = r.json()
    refs = data["references"]
    assert data["total"] == 7
    assert refs["deals"][0]["title"] == "Pizza 40% off"
    assert refs["deals"][0]["derived_status"] == "active"
    dec = refs["decisions"][0]
    assert dec["as"] == "source"
    assert dec["derived_status"] == "committed"
    assert refs["briefs"][0]["question"] == "what offers?"
    assert refs["digests"][0]["period_start"] == "2026-11-01"
    assert refs["alerts"][0]["watchlist_name"] == "pizza"
    assert refs["faqs"][0]["as"] == "question"
    assert refs["entities"][0]["name"] == "Pizza Hut"
    # the message itself carries its verified link
    assert data["message"]["tg_link"]
    # no thread for a root message
    assert data["thread"]["parent"] is None
    assert data["thread"]["replies"] == []


def test_evidence_followup_and_thread(api_client):
    with db.get_db() as conn:
        seed_all_kinds(conn)
        # make msg 2 a direct reply to msg 1 (reply_to captured v0.5+)
        conn.execute("UPDATE messages SET reply_to=1 WHERE chat_id=-1 "
                     "AND msg_id=2")
        conn.commit()

    # msg 2: referenced as a decision FOLLOW-UP, and sits in msg 1's thread
    r = api_client.get("/api/evidence", params={"chat_id": -1, "msg_id": 2})
    data = r.json()
    dec = data["references"]["decisions"][0]
    assert dec["as"] == "followup"
    assert dec["matched_terms"] == ["pizza", "offer"]
    assert data["thread"]["parent"]["msg_id"] == 1

    # and from msg 1's side, msg 2 shows as a reply
    r = api_client.get("/api/evidence", params={"chat_id": -1, "msg_id": 1})
    replies = r.json()["thread"]["replies"]
    assert [m["msg_id"] for m in replies] == [2]


def test_evidence_404_and_empty(api_client):
    with db.get_db() as conn:
        db.upsert_chat(conn, -1, "Dealz", "dealz", "group")
        db.upsert_message(conn, -1, 1, iso(1), 1, "ali", "plain message")
        conn.commit()

    r = api_client.get("/api/evidence", params={"chat_id": -1, "msg_id": 99})
    assert r.status_code == 404

    r = api_client.get("/api/evidence", params={"chat_id": -1, "msg_id": 1})
    data = r.json()
    assert data["total"] == 0
    assert all(v == [] for v in data["references"].values())
