"""Search matrix: representative content types through the real API.

Covers Arabic, English, mixed text, numbers/dates, special characters,
emojis, very long messages, media-only (empty text), similar and repeated
words - the full Phase-C search matrix from the release audit.
"""
import json

import db

CHAT = -7


def seed_matrix(api_client):
    msgs = [
        # (id, date, text)
        (1, "2026-01-01", "عرض خاص على البيتزا اليوم فقط"),
        (2, "2026-01-02", "Special pizza offer today only"),
        (3, "2026-01-03", "عرض pizza mix مطاعم discount خصم"),  # mixed line
        (4, "2026-01-04", "meeting on 2026-01-05 at 10:30 room 12"),
        (5, "2026-01-05", "price: 199.99 SAR ~ 20% off (in-store only!)"),
        (6, "2026-01-06", "great deal!! 🔥🍕 #discount #pizza_offer"),
        (7, "2026-01-07", "x" * 5000),  # very long message
        (8, "2026-01-08", ""),  # media-only (empty text)
        (9, "2026-01-09", "color colour"),  # similar words
        (10, "2026-01-10", "spam spam spam spam"),  # repeated words
        (11, "2026-01-11", "عرض خاص على البيتزا اليوم فقط"),  # exact dup of 1
        (12, "2026-01-12", "المطاعم أرقام الهاتف ٠١٢٣٤٥٦٧٨٩"),  # Arabic-Indic digits
    ]
    c = db.get_db()
    try:
        db.upsert_chat(c, CHAT, "Matrix", "matrix", "group")
        for mid, day, text in msgs:
            db.upsert_message(c, CHAT, mid, f"{day}T10:00:00+00:00",
                              1, "tester", text, has_media=1 if mid == 8 else 0)
        c.commit()
    finally:
        c.close()


def search(api_client, q, **params):
    p = {"q": q, "groups": str(CHAT)}
    p.update(params)
    r = api_client.get("/api/search?" + "&".join(
        f"{k}={v}" for k, v in p.items() if v))
    return r.json()


def test_arabic_exact_and_normalized(api_client):
    seed_matrix(api_client)
    hits = search(api_client, "عرض خاص")
    ids = {h["msg_id"] for h in hits}
    assert ids == {1, 11}, "exact Arabic phrase must match (incl. duplicate)"

    # taa marbuta normalization: searching with ه ending finds ة text
    hits = search(api_client, "المطاعم")
    assert {h["msg_id"] for h in hits} == {12}

    # alef variants: searching with أ matches plain ا
    hits = search(api_client, "ارقام")
    assert {h["msg_id"] for h in hits} == {12}


def test_english_and_mixed(api_client):
    seed_matrix(api_client)
    # "pizza offer" as a phrase: msg 2 only. msg 6's #pizza_offer keeps the
    # underscore (word char) so it is a single token - not the phrase.
    assert {h["msg_id"] for h in search(api_client, "pizza offer")} == {2}
    # underscored token matches on its own
    assert {h["msg_id"] for h in search(api_client, "pizza_offer")} == {6}
    # pipe alternatives: english OR arabic
    hits = search(api_client, "pizza|خصم")
    assert {h["msg_id"] for h in hits} == {2, 3, 6}


def test_numbers_dates_and_specials(api_client):
    seed_matrix(api_client)
    assert {h["msg_id"] for h in search(api_client, "199.99")} == {5}
    assert {h["msg_id"] for h in search(api_client, "2026-01-05")} == {4}
    assert {h["msg_id"] for h in search(api_client, "20% off")} == {5}
    # punctuation-heavy phrase
    assert {h["msg_id"] for h in search(api_client, "in-store only")} == {5}


def test_emoji_message_is_searchable_by_text(api_client):
    seed_matrix(api_client)
    hits = search(api_client, "discount")
    assert 6 in {h["msg_id"] for h in hits}


def test_long_message_and_media_only(api_client):
    seed_matrix(api_client)
    hits = search(api_client, "x" * 200)
    assert {h["msg_id"] for h in hits} == {7}, "long message must be indexed"
    # media-only: no text -> not searchable, but browsable
    assert search(api_client, "image") == []
    page = api_client.get(f"/api/messages?groups={CHAT}&limit=50").json()
    assert 8 in {m["msg_id"] for m in page["messages"]}


def test_similar_and_repeated_words(api_client):
    seed_matrix(api_client)
    assert {h["msg_id"] for h in search(api_client, "color")} == {9}
    assert {h["msg_id"] for h in search(api_client, "spam")} == {10}


def test_empty_results_and_date_filter_combo(api_client):
    seed_matrix(api_client)
    assert search(api_client, "nothing-matches-this") == []
    # date filter combines with text: "only" appears in msgs 2 (2026-01-02,
    # excluded by the filter) and 5 (2026-01-05, included)
    hits = search(api_client, "only", **{"from_": "2026-01-05"})
    assert {h["msg_id"] for h in hits} == {5}
    # sender filter narrows within a group
    hits = search(api_client, "pizza", **{"sender": "nobody"})
    assert hits == []


def test_search_response_shape_is_frontend_safe(api_client):
    seed_matrix(api_client)
    hits = search(api_client, "pizza")
    for h in hits:
        assert set(h) >= {"chat_id", "msg_id", "date", "sender_name",
                          "text", "has_media", "edited", "chat_title"}
        json.dumps(h)  # must be JSON-serializable (no stray types)
