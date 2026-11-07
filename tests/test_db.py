"""Database tests: migrations, upserts, incremental FTS, browse, search."""
import db


def add_msg(conn, chat_id, msg_id, date, text, sender="alice", media=0, edited=0):
    # real sync always upserts the chat first; tests must too
    db.upsert_chat(conn, chat_id, "Test", "testgroup", "group")
    db.upsert_message(conn, chat_id, msg_id, date, 1, sender, text,
                      has_media=media, edited=edited)


def test_fresh_init_and_migration(conn):
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(chats)")]
    assert "backfill_floor" in cols
    ver = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
    assert ver["value"] == str(db.SCHEMA_VERSION)


def test_reopen_uses_same_schema(conn):
    path = conn.execute("PRAGMA database_list").fetchone()["file"]
    conn.commit()
    c2 = db.get_db(path)
    assert c2.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"] == 0
    c2.close()


def test_upsert_and_incremental_fts(conn):
    add_msg(conn, -1, 1, "2026-01-01T10:00:00+00:00", "hello world offer")
    assert len(db.search(conn, ["hello world"])) == 1
    # update: text replaced, index follows, no duplicates
    add_msg(conn, -1, 1, "2026-01-01T10:00:00+00:00", "totally different now")
    assert len(db.search(conn, ["hello world"])) == 0
    assert len(db.search(conn, ["totally different"])) == 1
    # second message, arabic, normalization (alef variants + taa marbuta)
    add_msg(conn, -1, 2, "2026-01-02T10:00:00+00:00", "خصم خاص على المطاعم")
    assert len(db.search(conn, ["خصم"])) == 1
    assert len(db.search(conn, ["مطاعم"])) == 1  # ة normalized to ه


def test_browse_pagination_and_filters(conn):
    for i in range(1, 11):
        add_msg(conn, -1, i, f"2026-01-0{i % 9 + 1}T12:00:00+00:00", f"msg {i}",
                sender=f"s{i % 2}")
    db.upsert_chat(conn, -1, "Test", "testgroup", "group")

    p1 = db.browse(conn, limit=4)
    assert len(p1[0]) == 4 and p1[2] and p1[1]
    p2 = db.browse(conn, cursor=p1[1], limit=4)
    keys1 = {(m["chat_id"], m["msg_id"]) for m in p1[0]}
    keys2 = {(m["chat_id"], m["msg_id"]) for m in p2[0]}
    assert not keys1 & keys2
    # newest first
    assert p1[0][0]["date"] >= p1[0][-1]["date"]

    asc = db.browse(conn, sort="asc", limit=10)
    assert asc[0][0]["date"] <= asc[0][-1]["date"]

    only2 = db.browse(conn, sender="s2", limit=10)
    assert all(m["sender_name"] == "s2" for m in only2[0])

    ranged = db.browse(conn, date_from="2026-01-02", date_to="2026-01-03")
    assert all("2026-01-02" <= m["date"][:10] <= "2026-01-03" for m in ranged[0])


def test_search_multilingual_and_dedupe(conn):
    add_msg(conn, -1, 1, "2026-01-01T10:00:00+00:00", "special discount عرض خاص")
    add_msg(conn, -1, 2, "2026-01-02T10:00:00+00:00", "SPECIAL discount عرض خاص")
    db.upsert_chat(conn, -1, "Test", None, "group")
    rows = db.search(conn, ["special discount", "عرض خاص"], require_all=False)
    assert len(rows) == 2
    # OR semantics: any phrase matches
    rows = db.search(conn, ["عرض خاص"], require_all=False)
    assert len(rows) == 2


def test_senders_and_stats(conn):
    add_msg(conn, -1, 1, "2026-01-01T10:00:00+00:00", "a", sender="x")
    add_msg(conn, -1, 2, "2026-01-02T10:00:00+00:00", "b", sender="x")
    add_msg(conn, -1, 3, "2026-01-03T10:00:00+00:00", "c", sender="y")
    db.upsert_chat(conn, -1, "T", None, "group")
    senders = db.senders(conn)
    assert senders[0]["sender_name"] == "x" and senders[0]["count"] == 2
    s = db.stats(conn)
    assert s["messages"] == 3 and s["chats"] == 1
    # pending backfills: tracked chat with last_msg_id=0 counts as pending
    assert s["pending_backfills"] == 1


def test_backfill_progress_checkpoints(conn):
    db.upsert_chat(conn, -1, "T", None, "group")
    db.set_backfill_progress(conn, -1, 500, 300)
    last, _, floor = db.get_sync_state(conn, -1)
    assert (last, floor) == (500, 300)
    db.set_backfill_progress(conn, -1, 600, 0)
    assert db.get_sync_state(conn, -1)[2] == 0  # complete
