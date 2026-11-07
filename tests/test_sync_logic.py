"""Sync logic tests with a fake Telethon client: checkpoints, resume, cancel.

No network, no Telegram - just the orchestration logic against a temp DB.
"""
import asyncio
from datetime import datetime, timezone

import db
import sync


class FakeMsg:
    def __init__(self, id, date=None, text="hello", sender=None):
        self.id = id
        self.date = date or datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.message = text
        self.sender_id = 1
        self.sender = sender
        self.media = None
        self.edit_date = None


class FakeIter:
    """Yields ids [newest .. oldest]; honors max_id/min_id like Telethon."""

    def __init__(self, ids):
        self.ids = list(ids)
        self.pos = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.pos >= len(self.ids):
            raise StopAsyncIteration
        v = self.ids[self.pos]
        self.pos += 1
        return FakeMsg(v)


class FakeChat:
    def __init__(self, cid, title="Fake Group"):
        self.id = cid
        self.title = title
        self.username = "fake"
        self.megagroup = True


class FakeClient:
    """Emulates a small group with ids 1..1200 (newest = 1200)."""

    def __init__(self):
        self.ids = list(range(1200, 0, -1))  # iteration order: newest first

    async def get_entity(self, cid):
        return FakeChat(cid)

    def iter_messages(self, chat, wait_time=1, **kw):
        ids = self.ids
        if "max_id" in kw:
            ids = [i for i in ids if i <= kw["max_id"]]
        if "min_id" in kw:
            ids = [i for i in ids if i > kw["min_id"]]
        return FakeIter(ids)


def run(coro):
    return asyncio.run(coro)


def test_backfill_checkpoints_and_resume(conn):
    client = FakeClient()
    db.upsert_chat(conn, -1, "Fake Group", "fake", "group")

    # sync with a cancel after ~600 messages: stop by pre-setting CANCEL
    # via a wrapper that flips the event inside iteration
    class CancelAfter(FakeClient):
        def __init__(self, inner, after):
            super().__init__()
            self.inner = inner
            self.after = after
            self.ids = list(inner.ids)
            self.seen = 0

        def iter_messages(self, chat, wait_time=1, **kw):
            outer = self

            class CIter(FakeIter):
                async def __anext__(self):
                    if outer.seen >= outer.after:
                        sync.CANCEL.set()
                        raise StopAsyncIteration
                    outer.seen += 1
                    return await super().__anext__()
            ids = outer.ids
            if "max_id" in kw:
                ids = [i for i in ids if i <= kw["max_id"]]
            if "min_id" in kw:
                ids = [i for i in ids if i > kw["min_id"]]
            return CIter(ids)

    sync.CANCEL.clear()
    ca = CancelAfter(client, after=600)
    run(sync.sync_chat(ca, conn, -1))

    last, _, floor = db.get_sync_state(conn, -1)
    n_stored = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
    assert n_stored == 600
    assert floor > 0, "checkpoint must be saved on cancel"

    # resume: new fake client continues below the floor
    sync.CANCEL.clear()
    run(sync.sync_chat(FakeClient(), conn, -1))
    n_stored = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
    _, _, floor2 = db.get_sync_state(conn, -1)
    assert n_stored == 1200, "resume completes the full history"
    assert floor2 == 0, "floor cleared when backfill completes"


def test_incremental_fetches_only_new(conn):
    client = FakeClient()
    db.upsert_chat(conn, -1, "Fake Group", "fake", "group")
    # initial backfill of everything
    sync.CANCEL.clear()
    run(sync.sync_chat(client, conn, -1))
    assert conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"] == 1200
    last, _, _ = db.get_sync_state(conn, -1)
    assert last == 1200

    # add "new" messages by id and sync incrementally
    client.ids = [1203, 1202, 1201, 1200, 1199]
    client.ids = [1203, 1202, 1201]
    run(sync.sync_chat(FakeClient(), conn, -1))  # fresh full map: nothing new
    # simulate: client returns only ids > 1200
    class NewOnly(FakeClient):
        def __init__(self):
            super().__init__()
            self.ids = [1203, 1202, 1201]

    run(sync.sync_chat(NewOnly(), conn, -1))
    ids = {r["msg_id"] for r in conn.execute("SELECT msg_id FROM messages")}
    assert {1201, 1202, 1203} <= ids


def test_cancel_event_stops_iteration(conn):
    db.upsert_chat(conn, -1, "Fake Group", "fake", "group")
    sync.CANCEL.set()
    got = []
    client = FakeClient()

    async def consume():
        async for m in sync.iter_with_flood_retry(client, -1):
            got.append(m.id)

    run(consume())
    assert got == [], "a pre-set cancel must stop iteration before any yield"
    sync.CANCEL.clear()
