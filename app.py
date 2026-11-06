"""Local web app: browse/search/AI Q&A over synced Telegram messages.

Run:  python app.py   ->  http://127.0.0.1:8000
"""
import asyncio
import collections
import io
import os
import sys
import threading
import time

from dotenv import load_dotenv

load_dotenv()

import ai
import db
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
HERE = os.path.dirname(os.path.abspath(__file__))

SYNC_DAYS = int(os.environ.get("SYNC_DAYS", "3"))  # rescan window for the UI button

TELEGRAM_CONFIGURED = bool(os.environ.get("TELEGRAM_API_ID")
                           and os.environ.get("TELEGRAM_API_HASH"))


# ---------------------------------------------------------------------------
# Background job runner: jobs run one at a time; extra jobs queue up in order.
# ---------------------------------------------------------------------------

class JobRunner:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.name = ""
        self.log = ""
        self.result = None
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
        self.result = None
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
        result = None
        try:
            try:
                result = func()
            except SystemExit:
                ok = False
            except Exception as e:
                buf.write(f"job failed: {e}\n")
                ok = False
        finally:
            sys.stdout = old_stdout
        with self.lock:
            self.log = buf.getvalue()
            self.result = result
            self.last_done = {"name": name, "ok": ok,
                              "finished_at": time.time()}
            self.running = False
            if self.queue:
                self._start_next_locked()


JOBS = JobRunner()


class _Args:
    def __init__(self, days=None, track=None):
        self.list = False
        self.track = track
        self.untrack = None
        self.full = False
        self.days = days
        self.interactive = False


def _run_sync(days=None, track=None):
    from sync import run as sync_run
    asyncio.run(sync_run(_Args(days=days, track=track)))


DIALOGS = {"list": None}  # cached dialog list; survives across jobs


def _fetch_dialogs():
    from sync import fetch_dialogs
    result = asyncio.run(fetch_dialogs())
    DIALOGS["list"] = result
    return result


def parse_groups(raw):
    out = []
    for part in (raw or "").split(","):
        part = part.strip()
        try:
            out.append(int(part))
        except ValueError:
            pass
    return out


app = FastAPI(title="Telegram Query")
db.init_db()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str


class TrackRequest(BaseModel):
    chat_ids: list[int]


class UntrackRequest(BaseModel):
    chat_ids: list[int]


class StopRequest(BaseModel):
    clear_queue: bool = False


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


@app.get("/api/stats")
def api_stats():
    conn = db.get_db()
    try:
        s = db.stats(conn)
        s["ai_configured"] = ai.is_configured()
        return s
    finally:
        conn.close()


@app.get("/api/groups")
def api_groups():
    conn = db.get_db()
    try:
        rows = conn.execute("""
            SELECT c.chat_id, c.title, c.kind, c.username, c.last_synced,
                   COUNT(m.msg_id) AS message_count, MAX(m.date) AS last_message
            FROM chats c LEFT JOIN messages m ON m.chat_id = c.chat_id
            WHERE c.tracked = 1
            GROUP BY c.chat_id ORDER BY c.title COLLATE NOCASE
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/messages")
def api_messages(groups: str = "", sender: str = "", from_: str = "",
                 to: str = "", media: int = None, cursor: str = "",
                 limit: int = 50, sort: str = "desc"):
    conn = db.get_db()
    try:
        rows, next_cursor, has_more = db.browse(
            conn,
            chat_ids=parse_groups(groups) or None,
            sender=sender or None,
            date_from=from_ or None,
            date_to=to or None,
            media=media,
            cursor=cursor or None,
            limit=min(limit, 200),
            sort=sort,
        )
        return {"messages": rows, "next_cursor": next_cursor, "has_more": has_more}
    finally:
        conn.close()


@app.get("/api/senders")
def api_senders(groups: str = ""):
    conn = db.get_db()
    try:
        return db.senders(conn, chat_ids=parse_groups(groups) or None)
    finally:
        conn.close()


@app.get("/api/search")
def api_search(q: str = "", groups: str = "", sender: str = "",
               from_: str = "", to: str = "", limit: int = 200):
    if not q.strip():
        return []
    conn = db.get_db()
    try:
        return db.search(
            conn,
            [p.strip() for p in q.split("|") if p.strip()],  # | = multiple phrases
            chat_ids=parse_groups(groups) or None,
            sender=sender or None,
            date_from=from_ or None,
            date_to=to or None,
            require_all=False,  # any-phrase match; ranking favors multi-hits
            limit=min(limit, 500),
        )
    finally:
        conn.close()


@app.post("/api/ask")
def api_ask(req: AskRequest):
    conn = db.get_db()
    try:
        result = ai.ask(conn, req.question)
        sources = result.pop("sources", [])
        result["sources"] = [
            {k: m[k] for k in ("chat_title", "date", "sender_name", "text", "has_media")}
            for m in sources
        ]
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Jobs: sync / dialogs / track / untrack
# ---------------------------------------------------------------------------

@app.post("/api/sync")
def api_sync(days: int = None):
    if not TELEGRAM_CONFIGURED:
        return JSONResponse({"error": "Telegram credentials not configured"},
                            status_code=400)
    with JOBS.lock:
        queued_behind = ([JOBS.name] if JOBS.running else []) + \
                        [n for n, _ in JOBS.queue]
    started = JOBS.start("sync", lambda: _run_sync(days=days))
    if not started:
        return {"started": False, "reason": "already_queued"}
    return {"started": True, "queued_behind": queued_behind}


@app.post("/api/job/stop")
def api_job_stop(req: StopRequest = None):
    """Ask the running job to stop at its next checkpoint.
    clear_queue=True also drops every queued (not yet started) job."""
    dropped = []
    with JOBS.lock:
        if req and req.clear_queue:
            while JOBS.queue:
                dropped.append(JOBS.queue.popleft()[0])
    stopping = False
    if JOBS.running:
        from sync import CANCEL
        CANCEL.set()
        stopping = True
    return {"stopping": stopping, "cleared": dropped}


@app.get("/api/job/status")
def api_job_status():
    with JOBS.lock:
        return {"running": JOBS.running, "name": JOBS.name, "log": JOBS.log,
                "queued": [n for n, _ in JOBS.queue],
                "last_done": JOBS.last_done}


def _tracked_ids():
    conn = db.get_db()
    try:
        return {r["chat_id"] for r in
                conn.execute("SELECT chat_id FROM chats WHERE tracked=1").fetchall()}
    finally:
        conn.close()


@app.post("/api/dialogs")
def api_dialogs_start():
    if not TELEGRAM_CONFIGURED:
        return JSONResponse({"error": "Telegram credentials not configured"},
                            status_code=400)
    # front=True: the listing is quick and unblocks the Manage UI
    started = JOBS.start("dialogs", _fetch_dialogs, front=True)
    return {"started": started, "reason": None if started else "already_pending"}


@app.get("/api/dialogs")
def api_dialogs_get():
    if DIALOGS["list"] is not None:
        tracked = _tracked_ids()
        return {"ready": True,
                "dialogs": [{**d, "tracked": d["chat_id"] in tracked}
                            for d in DIALOGS["list"]]}
    return {"ready": False}


@app.post("/api/groups/track")
def api_track(req: TrackRequest):
    if not req.chat_ids:
        return JSONResponse({"error": "chat_ids required"}, status_code=400)
    if not TELEGRAM_CONFIGURED:
        return JSONResponse({"error": "Telegram credentials not configured"},
                            status_code=400)
    tracked = _tracked_ids()
    new_ids = [cid for cid in req.chat_ids if cid not in tracked]
    if not new_ids:
        return {"started": False, "reason": "already_tracked"}
    with JOBS.lock:
        queued_behind = ([JOBS.name] if JOBS.running else []) + \
                        [n for n, _ in JOBS.queue]
    JOBS.start("track", lambda: _run_sync(track=new_ids))
    return {"started": True, "chat_ids": new_ids, "queued_behind": queued_behind}


@app.post("/api/groups/untrack")
def api_untrack(req: UntrackRequest):
    if not req.chat_ids:
        return JSONResponse({"error": "chat_ids required"}, status_code=400)
    conn = db.get_db()
    try:
        for cid in req.chat_ids:
            conn.execute("UPDATE chats SET tracked=0 WHERE chat_id=?", (cid,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
