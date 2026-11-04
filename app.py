"""Local web app: search UI + AI Q&A over synced Telegram messages.

Run:  python app.py   ->  http://127.0.0.1:8000
"""
import asyncio
import contextlib
import io
import os
import sys
import threading
import time
from datetime import datetime, timezone

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


# ---------------------------------------------------------------------------
# Sync bridge: run sync.py's logic in-process (log output captured for the UI)
# ---------------------------------------------------------------------------

SYNC_DAYS = int(os.environ.get("SYNC_DAYS", "3"))  # rescan window for the UI button


class SyncState:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.log = ""
        self.finished_at = None
        self.ok = None

    def start(self, days=None):
        with self.lock:
            if self.running:
                return False
            self.running = True
            self.log = ""
            self.ok = None
            threading.Thread(target=self._run, args=(days,), daemon=True).start()
            return True

    def write(self, text):
        with self.lock:
            self.log += text

    def _run(self, days):
        buf = io.StringIO()

        class Tee(io.TextIOBase):
            def write(self, s):
                buf.write(s)
                SyncState_.write(s)
                return len(s)

        old_stdout = sys.stdout
        sys.stdout = Tee()
        try:
            rc = 0
            try:
                from sync import run as sync_run
                asyncio.run(sync_run(_Args(days=days if days is not None else SYNC_DAYS)))
            except SystemExit:
                rc = 1
            except Exception as e:
                buf.write(f"sync failed: {e}\n")
                rc = 1
            self.ok = rc == 0
        finally:
            sys.stdout = old_stdout
            self.log = buf.getvalue()
            self.running = False
            self.finished_at = time.time()


SyncState_ = SyncState()
SYNC = SyncState_


class _Args:
    def __init__(self, days=None):
        self.list = False
        self.track = None
        self.untrack = None
        self.full = False
        self.days = days
        self.interactive = False

app = FastAPI(title="Telegram Query")
db.init_db()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str


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
        rows = conn.execute(
            "SELECT chat_id, title, kind, last_synced FROM chats "
            "WHERE tracked=1 ORDER BY title").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/search")
def api_search(q: str = "", group: int = None, sender: str = "",
               from_: str = "", to: str = "", limit: int = 200):
    if not q.strip():
        return []
    conn = db.get_db()
    try:
        return db.search(
            conn,
            [p.strip() for p in q.split("|") if p.strip()],  # | = multiple phrases
            chat_ids=[group] if group else None,
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


@app.post("/api/sync")
def api_sync(days: int = None):
    if not (os.environ.get("TELEGRAM_API_ID") and os.environ.get("TELEGRAM_API_HASH")):
        return JSONResponse({"error": "Telegram credentials not configured"},
                            status_code=400)
    started = SYNC.start(days=days)
    return {"started": started, "running": SYNC.running}


@app.get("/api/sync/status")
def api_sync_status():
    return {"running": SYNC.running, "log": SYNC.log, "ok": SYNC.ok,
            "finished_at": SYNC.finished_at}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
