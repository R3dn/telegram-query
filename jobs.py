"""Background job management for Telegram Query.

Jobs run ONE AT A TIME (the Telegram session is a single SQLite file that
must not be used concurrently); extra jobs queue up in order. Anything a
job prints to stdout is captured and streamed to the UI via
``GET /api/job/status``.

Job names: sync | track | dialogs | auth
"""
from __future__ import annotations

import asyncio
import collections
import io
import sys
import threading
import time

__all__ = ["JOBS", "JobRunner", "run_sync_job", "fetch_dialogs_job",
           "DIALOGS_CACHE"]


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
        sync/dialogs are deduped; front=True jumps ahead of other queued jobs."""
        with self.lock:
            if name in ("sync", "dialogs"):
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


def fetch_dialogs_job():
    """List every group/channel dialog of the logged-in account."""
    from sync import fetch_dialogs
    result = asyncio.run(fetch_dialogs())
    DIALOGS_CACHE["list"] = result
    return result
