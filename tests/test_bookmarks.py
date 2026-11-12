"""Bookmarks + notes tests: star, note, filter, search, deletion behavior."""
from contextlib import closing
from datetime import datetime, timedelta, timezone

import db


def iso(days_ago, hour=10):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)
            ).replace(hour=hour).isoformat()


def seed(api_client):
    """Two chats, a few messages; returns (chat_id, msg_id) tuples."""
    with closing(db.get_db()) as conn:
        db.upsert_chat(conn, -1001234567890, "Dealz", "dealz", "group")
        db.upsert_chat(conn, -40, "Basic group", None, "group")
        ids = []
        for i in range(1, 4):
            db.upsert_message(conn, -1001234567890, i, iso(1), 1, "s",
                              f"best pizza deal code P{i}")
            ids.append((-1001234567890, i))
        db.upsert_message(conn, -40, 1, iso(2), 1, "b",
                          "old school message without a link")
        conn.commit()
    return ids


def test_star_and_browse_flag(api_client):
    ids = seed(api_client)
    r = api_client.post("/api/bookmarks",
                        json={"chat_id": ids[0][0], "msg_id": ids[0][1],
                              "note": "احفظ هذا العرض"})
    assert r.status_code == 200

    page = api_client.get("/api/messages").json()
    by_key = {(m["chat_id"], m["msg_id"]): m for m in page["messages"]}
    assert by_key[(-1001234567890, 1)]["bookmarked"] == 1
    assert by_key[(-1001234567890, 1)]["bookmark_note"] == "احفظ هذا العرض"
    assert by_key[(-1001234567890, 2)]["bookmarked"] == 0


def test_bookmarked_filter_in_browse_and_search(api_client):
    ids = seed(api_client)
    api_client.post("/api/bookmarks",
                    json={"chat_id": ids[0][0], "msg_id": ids[0][1]})

    rows = api_client.get("/api/messages?bookmarked=true").json()["messages"]
    assert {m["msg_id"] for m in rows} == {1}

    hits = api_client.get("/api/search?q=pizza&bookmarked=true").json()
    assert {h["msg_id"] for h in hits} == {1}


def test_note_edit_and_delete(api_client):
    ids = seed(api_client)
    cid, mid = ids[1]
    api_client.post("/api/bookmarks", json={"chat_id": cid, "msg_id": mid})
    api_client.post("/api/bookmarks",
                    json={"chat_id": cid, "msg_id": mid, "note": "updated note"})
    rows = api_client.get("/api/bookmarks").json()
    assert rows[0]["note"] == "updated note"

    assert api_client.delete(f"/api/bookmarks/{cid}/{mid}"
                             ).status_code == 200
    assert api_client.delete(f"/api/bookmarks/{cid}/{mid}"
                             ).status_code == 404
    assert api_client.get("/api/bookmarks").json() == []


def test_bookmark_requires_existing_message(api_client):
    seed(api_client)
    r = api_client.post("/api/bookmarks",
                        json={"chat_id": -999, "msg_id": 42})
    assert r.status_code == 404


def test_note_search_and_group_filter(api_client):
    ids = seed(api_client)
    for cid, mid in ids[:2]:
        api_client.post("/api/bookmarks",
                        json={"chat_id": cid, "msg_id": mid,
                              "note": "متابعة الاسبوع القادم"})
    api_client.post("/api/bookmarks",
                    json={"chat_id": -40, "msg_id": 1,
                          "note": "engine note"})
    # Arabic note search
    rows = api_client.get("/api/bookmarks",
                          params={"q": "الاسبوع"}).json()
    assert len(rows) == 2
    # group filter
    rows = api_client.get("/api/bookmarks?groups=-40").json()
    assert len(rows) == 1 and rows[0]["note"] == "engine note"
    # message-text search through bookmarks
    rows = api_client.get("/api/bookmarks",
                          params={"q": "old school"}).json()
    assert len(rows) == 1 and rows[0]["note"] == "engine note"


def test_untrack_delete_cascades_to_bookmarks(api_client):
    ids = seed(api_client)
    for cid, mid in ids:
        api_client.post("/api/bookmarks", json={"chat_id": cid, "msg_id": mid})
    r = api_client.post("/api/groups/untrack",
                        json={"chat_ids": [-40], "delete_messages": True})
    assert r.json()["ok"] is True
    rows = api_client.get("/api/bookmarks").json()
    assert all(b["chat_id"] != -40 for b in rows), "no orphaned bookmarks"
    assert len(rows) == 3
