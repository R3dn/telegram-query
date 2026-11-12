"""Sync logic tests with a fake Telethon client: checkpoints, resume, cancel.

No network, no Telegram - just the orchestration logic against a temp DB.
"""
import asyncio
from datetime import datetime, timezone

from telethon.errors import ChatIdInvalidError

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


def test_dead_chat_is_skipped_not_fatal(conn, capsys):
    """A chat Telegram can no longer resolve (deleted, migrated to a
    supergroup, account left/kicked) is skipped with the chat's title and
    an untrack hint - one dead group must not abort the whole sync job."""
    db.upsert_chat(conn, -200, "Dead Group", "dead", "group")

    class DeadClient(FakeClient):
        async def get_entity(self, cid):
            raise ChatIdInvalidError(request=None)

    sync.CANCEL.clear()
    run(sync.sync_chat(DeadClient(), conn, -200))  # must not raise

    out = capsys.readouterr().out
    assert "[Dead Group]" in out, "the skip line must name the chat"
    assert "skipped - chat ID is invalid" in out
    assert "python sync.py --untrack -200" in out
    assert conn.execute(
        "SELECT COUNT(*) c FROM messages WHERE chat_id=-200"
    ).fetchone()["c"] == 0, "nothing is stored for a dead chat"


def test_transient_resolution_error_is_skipped(conn, capsys):
    """Any other get_entity failure (e.g. a network error) skips that one
    chat with the raw error - the job keeps going."""
    db.upsert_chat(conn, -300, "Flaky Group", "flaky", "group")

    class FlakyClient(FakeClient):
        async def get_entity(self, cid):
            raise ValueError("connection reset mid-handshake")

    sync.CANCEL.clear()
    run(sync.sync_chat(FlakyClient(), conn, -300))  # must not raise

    out = capsys.readouterr().out
    assert "[Flaky Group] skipped - could not resolve the chat" in out
    assert "connection reset mid-handshake" in out
    assert conn.execute(
        "SELECT COUNT(*) c FROM messages WHERE chat_id=-300"
    ).fetchone()["c"] == 0


def test_alive_chat_still_syncs_after_a_dead_one(conn, capsys):
    """The run() loop calls sync_chat per tracked chat; after the skip
    change the dead chat returns and the next chat syncs normally."""
    db.upsert_chat(conn, -400, "Zombie Group", "zombie", "group")
    db.upsert_chat(conn, -401, "Alive Group", "alive", "group")

    class MixedClient(FakeClient):
        async def get_entity(self, cid):
            if cid == -400:
                raise ChatIdInvalidError(request=None)
            return FakeChat(cid)

    sync.CANCEL.clear()
    run(sync.sync_chat(MixedClient(), conn, -400))  # skipped, no raise
    run(sync.sync_chat(MixedClient(), conn, -401))  # still works

    out = capsys.readouterr().out
    assert "[Zombie Group] skipped" in out
    assert conn.execute(
        "SELECT COUNT(*) c FROM messages WHERE chat_id=-401"
    ).fetchone()["c"] == 1200, "the live chat fully backfills"


# ---------------------------------------------------------------------------
# Fetch errors mid-fetch must never advance the watermark past unfetched
# messages (v1.0.2): messages arrive NEWEST-first, so a fetch that dies
# midway has stored the top of a range whose middle was never fetched.
# ---------------------------------------------------------------------------

class ExplodingIter(FakeIter):
    """Yields `good` messages, then raises like a dropped connection."""

    def __init__(self, ids, good):
        super().__init__(ids)
        self.good = good

    async def __anext__(self):
        if self.pos >= self.good or self.pos >= len(self.ids):
            raise ConnectionError("connection reset mid-fetch")
        return await super().__anext__()


class ExplodingClient(FakeClient):
    """A group with ids 1..1200 on Telegram; every fetch dies after
    `good` messages (newest first)."""

    def __init__(self, good):
        super().__init__()
        self.good = good

    def iter_messages(self, chat, wait_time=1, **kw):
        ids = self.ids
        if "max_id" in kw:
            ids = [i for i in ids if i <= kw["max_id"]]
        if "min_id" in kw:
            ids = [i for i in ids if i > kw["min_id"]]
        return ExplodingIter(ids, self.good)


def test_backfill_error_checkpoints_and_resumes(conn):
    """A full backfill that dies mid-fetch must checkpoint progress
    (exactly like a cancel) and resume on the next sync - never be
    reported as complete with most of the history missing."""
    db.upsert_chat(conn, -1, "Fake Group", "fake", "group")
    sync.CANCEL.clear()

    ok = run(sync.sync_chat(ExplodingClient(good=100), conn, -1, full=True))
    assert ok is False, "a failed fetch is a failed sync"
    last, _, floor = db.get_sync_state(conn, -1)
    n_stored = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
    assert n_stored == 100
    assert floor == 1101, "checkpoint below the oldest stored message (1101)"
    assert db.stats(conn)["pending_backfills"] == 1, \
        "the UI must show the backfill as pending"

    # resume with a healthy client completes the archive
    sync.CANCEL.clear()
    ok = run(sync.sync_chat(FakeClient(), conn, -1))
    assert ok is True
    assert conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"] \
        == 1200, "resume fills the entire history"
    _, _, floor2 = db.get_sync_state(conn, -1)
    assert floor2 == 0


def test_backfill_error_before_any_message_keeps_the_old_floor(conn):
    """A resumed backfill that dies before storing anything keeps the
    previous checkpoint - progress is never lost, never fabricated."""
    db.upsert_chat(conn, -1, "Fake Group", "fake", "group")
    db.set_backfill_progress(conn, -1, 1200, 1000)
    conn.commit()
    sync.CANCEL.clear()

    ok = run(sync.sync_chat(ExplodingClient(good=0), conn, -1))
    assert ok is False
    _, _, floor = db.get_sync_state(conn, -1)
    assert floor == 1000, "the pre-run checkpoint must survive untouched"


def test_incremental_error_keeps_the_pre_run_watermark(conn):
    """An incremental fetch that dies midway must NOT advance
    last_msg_id past messages Telegram never gave us: the 100 newest
    messages were stored, but the middle of the range (901..1100) was
    never fetched. The next sync re-walks from the old watermark and
    repairs the gap - duplicates are skipped by upsert."""
    db.upsert_chat(conn, -1, "Fake Group", "fake", "group")
    for i in range(1, 901):                       # previously synced history
        db.upsert_message(conn, -1, i, "2026-01-01T00:00:00+00:00",
                          1, "s", f"msg {i}")
    db.update_sync_state(conn, -1, 900)
    conn.commit()
    sync.CANCEL.clear()

    ok = run(sync.sync_chat(ExplodingClient(good=100), conn, -1))
    assert ok is False
    last, _, floor = db.get_sync_state(conn, -1)
    assert last == 900, "the watermark must not skip unfetched messages"
    assert floor == 0

    # recovery: a healthy sync must re-walk and fill the gap
    sync.CANCEL.clear()
    ok = run(sync.sync_chat(FakeClient(), conn, -1))
    assert ok is True
    stored = conn.execute(
        "SELECT COUNT(*) c FROM messages WHERE chat_id=-1").fetchone()["c"]
    assert stored == 1200, "the gap (901..1100) is fully repaired"
    last, _, _ = db.get_sync_state(conn, -1)
    assert last == 1200


def test_days_rescan_error_keeps_the_pre_run_watermark(conn):
    """A --days edit re-scan that dies midway keeps the old watermark:
    the re-scan window is idempotent (dupes skipped), but the watermark
    must never advance past a range whose middle was never fetched."""
    from datetime import datetime, timedelta, timezone

    recent = datetime.now(timezone.utc) - timedelta(hours=2)

    class RecentExplodingClient(ExplodingClient):
        """Same as ExplodingClient, but messages are dated inside the
        re-scan window (the stock fakes are dated 2026-01-01)."""

        def iter_messages(self, chat, wait_time=1, **kw):
            ids = self.ids
            if "max_id" in kw:
                ids = [i for i in ids if i <= kw["max_id"]]
            if "min_id" in kw:
                ids = [i for i in ids if i > kw["min_id"]]

            class _It(ExplodingIter):
                async def __anext__(self):
                    msg = await super().__anext__()
                    msg.date = recent
                    return msg
            return _It(ids, self.good)

    db.upsert_chat(conn, -1, "Fake Group", "fake", "group")
    db.update_sync_state(conn, -1, 1200)
    conn.commit()
    sync.CANCEL.clear()

    ok = run(sync.sync_chat(RecentExplodingClient(good=50), conn, -1, days=3))
    assert ok is False
    last, _, floor = db.get_sync_state(conn, -1)
    assert last == 1200 and floor == 0
    # the 50 re-scanned messages are real data - they stay stored
    assert conn.execute(
        "SELECT COUNT(*) c FROM messages WHERE chat_id=-1"
    ).fetchone()["c"] == 50

