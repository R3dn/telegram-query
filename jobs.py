"""Background job management for Telegram Query.

Jobs run ONE AT A TIME (the Telegram session is a single SQLite file that
must not be used concurrently); extra jobs queue up in order. Anything a
job prints to stdout is captured and streamed to the UI via
``GET /api/job/status``.

Job names: sync | track | dialogs | auth | reindex
"""
from __future__ import annotations

import asyncio
import collections
import io
import sys
import threading
import time

__all__ = ["JOBS", "JobRunner", "run_sync_job", "fetch_dialogs_job",
           "run_reindex_job", "run_discover_job", "POST_SYNC_HOOKS",
           "DIALOGS_CACHE"]

# Callables run after every SUCCESSFUL sync job (no args). Registered by
# features that need incremental work on new messages (v0.6 watchlists,
# v0.5 deals). Exceptions are logged, never fail the sync.
POST_SYNC_HOOKS = []

# Callables run from the scheduler tick (receive a db connection). Used by
# v0.6 digest schedules. Must stay cheap when nothing is due.
TICK_HOOKS = []


class JobRunner:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.name = ""
        self.log = ""
        self.queue = collections.deque()   # [(name, func), ...]
        self.last_done = None             # {"name", "ok", "finished_at"}

    def start(self, name, func, front=False):
        """Enqueue a job: runs immediately when idle, else after current ones.
        sync/dialogs/extract/brief are deduped; front=True jumps ahead of
        other queued jobs."""
        with self.lock:
            if name in ("sync", "dialogs", "extract", "brief", "digest", "faq",
                    "discover"):
                if (self.running and self.name == name) or \
                        any(n == name for n, _ in self.queue):
                    return False
            if front:
                self.queue.appendleft((name, func))
            else:
                self.queue.append((name, func))
            if not self.running:
                self._start_next_locked()
        return True

    def _start_next_locked(self):
        name, func = self.queue.popleft()
        self.running = True
        self.name = name
        self.log = ""
        threading.Thread(target=self._run, args=(name, func), daemon=True).start()

    def _live_log(self, text):
        with self.lock:
            self.log += text

    def _run(self, name, func):
        try:  # fresh job must not inherit a stale cancel request
            from sync import CANCEL
            CANCEL.clear()
        except ImportError:
            pass
        runner = self
        buf = io.StringIO()

        class Tee(io.TextIOBase):
            def write(self, s):
                buf.write(s)
                runner._live_log(s)
                return len(s)

        old_stdout = sys.stdout
        sys.stdout = Tee()
        ok = True
        try:
            try:
                func()
            except SystemExit:
                ok = False
            except Exception as e:
                buf.write(f"job failed: {e}\n")
                ok = False
        finally:
            sys.stdout = old_stdout
        with self.lock:
            self.log = buf.getvalue()
            self.last_done = {"name": name, "ok": ok,
                              "finished_at": time.time()}
            self.running = False
            if self.queue:
                self._start_next_locked()


JOBS = JobRunner()

# Cached dialog list (id -> {chat_id, title, username, kind}); survives
# across jobs so the Manage-groups dialog opens instantly after listing once.
DIALOGS_CACHE = {"list": None}


def run_sync_job(days=None, track=None):
    """Incremental sync (days rescan) or full track+backfill, as a job."""
    from sync import SyncArgs
    from sync import run as sync_run
    asyncio.run(sync_run(SyncArgs(days=days, track=track,
                                  login_interactive=False)))
    for hook in POST_SYNC_HOOKS:
        try:
            hook()
        except Exception as e:  # noqa: BLE001 - hooks never fail the sync
            print(f"post-sync hook {getattr(hook, '__name__', hook)} failed: {e}")


def run_reindex_job(path=None):
    """One-time reindex: rewrite text_norm for every message with the CURRENT
    normalization rules, rebuild the FTS index, clear the needs_reindex flag.

    Batched and cancellable (checked between batches; the flag stays set so
    the next app start retries it). Safe to re-run - always idempotent.
    ``path`` targets a specific database (tests); default = the app DB.
    """
    import config
    import db
    from sync import CANCEL

    conn = db.get_db(path)
    try:
        level = config.settings.normalization_level
        total = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
        print(f"Reindexing {total} messages (normalization: {level}) ...")
        done, last_rowid, batch = 0, 0, 5000
        while True:
            if CANCEL.is_set():
                print("Reindex paused - it will resume on the next app start "
                      "(or from Settings).")
                return
            rows = conn.execute(
                "SELECT rowid, text FROM messages WHERE rowid > ? "
                "ORDER BY rowid LIMIT ?",
                (last_rowid, batch)).fetchall()
            if not rows:
                break
            for r in rows:
                conn.execute("UPDATE messages SET text_norm=? WHERE rowid=?",
                             (db.normalize_text(r["text"] or ""), r["rowid"]))
            last_rowid = rows[-1]["rowid"]
            conn.commit()
            done += len(rows)
            print(f"  ... {done}/{total}")
        conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
        db.set_setting(conn, "needs_reindex", "0")
        db.set_setting(conn, "norm_level", level)
        conn.commit()
        print("Reindex complete - search is fully consistent again.")
    finally:
        conn.close()


def fetch_dialogs_job():
    """List every group/channel dialog of the logged-in account."""
    from sync import fetch_dialogs
    result = asyncio.run(fetch_dialogs())
    DIALOGS_CACHE["list"] = result
    return result


def run_extract_job(chat_ids=None, date_from=None, date_to=None):
    """Deals extraction over a scope (backfill), as a visible job."""
    import deals
    conn = db_get_db()
    try:
        print(f"[deals] extracting offers (scope: "
              f"{len(chat_ids) if chat_ids else 'all'} group(s)"
              f"{', {date_from}..{date_to}' if date_from or date_to else ''})")
        deals.extract(conn, chat_ids=chat_ids, date_from=date_from,
                      date_to=date_to)
    finally:
        conn.close()


def run_brief_job(brief_id):
    """Generate a research brief as a visible job. The brief row itself is
    persisted first (api/research.py), so a restart just needs a re-run."""
    import research
    conn = db_get_db()
    try:
        research.generate(conn, brief_id)
    finally:
        conn.close()


def run_digest_job(chat_ids=None, period_start=None, period_end=None,
                   frequency="daily", language="auto", schedule_id=None):
    """On-demand or scheduled digest, as a visible job."""
    import digests
    conn = db_get_db()
    try:
        digests.generate(conn, chat_ids=chat_ids, period_start=period_start,
                         period_end=period_end, frequency=frequency,
                         language=language, schedule_id=schedule_id)
    finally:
        conn.close()


def run_faq_job(chat_ids=None, days=90):
    """FAQ discovery over a scope, as a visible job."""
    import faq
    conn = db_get_db()
    try:
        faq.discover(conn, chat_ids=chat_ids, days=days)
    finally:
        conn.close()


def run_discover_job():
    """One-time/full discovery backfill (v0.7): term stats, the question
    radar over the full archive, and the entity gazetteer rebuild.
    Visible, cancellable, idempotent - clears the needs flag at the end."""
    import db
    import discover
    import entities
    conn = db_get_db()
    try:
        discover.rebuild(conn)
        entities.rebuild(conn)
        db.set_setting(conn, "needs_discover_backfill", "0")
        conn.commit()
        print("[discover] backfill complete")
    finally:
        conn.close()


def db_get_db():
    # local import to avoid a circular module dependency at load time
    import db
    return db.get_db()
