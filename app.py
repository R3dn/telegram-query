"""Telegram Query - local-first, searchable, AI-queryable archive for
your Telegram groups.

Run:  python app.py   ->  http://127.0.0.1:8000

Never expose this app on a public network without additional auth: the API
serves your complete message archive and is bound to 127.0.0.1 by default.
A Host-allowlist middleware additionally blocks cross-origin requests from
web pages (DNS rebinding / simple-form CSRF against local apps).
"""
from __future__ import annotations

import contextlib
import logging
import os
import threading

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import auth as tg_auth
import config
import db
import deals
import entities
import jobs
import scheduler
from api import ai as ai_api
from api import archive, general, groups
from api import auth as auth_api
from api import bookmarks as bookmarks_api
from api import deals as deals_api
from api import digests as digests_api
from api import discover as discover_api
from api import exports as exports_api
from api import faqs as faqs_api
from api import jobs as jobs_api
from api import monitor as monitor_api
from api import research as research_api
from api import saved as saved_api
from api import scheduler as scheduler_api
from api import setup as setup_api

logging.basicConfig(
    level=config.settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("tgq")

WEB_DIST = config.APP_ROOT / "web" / "dist"

db.init_db()


def _start_reindex_if_needed():
    """v0.4 upgrade: re-normalize existing archives once, as a visible job.
    Idempotent - the job itself clears the flag."""
    try:
        conn = db.get_db()
        try:
            if db.get_setting(conn, "needs_reindex") == "1":
                jobs.JOBS.start("reindex", jobs.run_reindex_job, front=True)
                log.info("normalization changed - reindex job queued")
        finally:
            conn.close()
    except Exception:
        log.exception("could not queue the reindex job")


def _start_discover_backfill_if_needed():
    """v0.7 upgrade: build discovery data (term stats, questions,
    entities) for existing archives once, as a visible job. Idempotent -
    the job itself clears the flag."""
    try:
        conn = db.get_db()
        try:
            if db.get_setting(conn, "needs_discover_backfill") == "1":
                jobs.JOBS.start("discover", jobs.run_discover_job, front=True)
                log.info("v0.7 upgrade - discovery backfill job queued")
        finally:
            conn.close()
    except Exception:
        log.exception("could not queue the discovery backfill job")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # check the Telegram session in the background (cheap, cached)
    threading.Thread(target=lambda: tg_auth.run(tg_auth.refresh_auth_state()),
                     daemon=True).start()
    # auto-sync scheduler (DB-persisted state; thread re-reads it per tick)
    threading.Thread(target=scheduler.run_loop, daemon=True,
                     name="tgq-scheduler").start()
    _start_reindex_if_needed()
    # v0.5: incremental deals extraction after each sync (no-op unless the
    # user enabled it; runs inside the sync job thread, never the UI thread)
    if deals.post_sync_hook not in jobs.POST_SYNC_HOOKS:
        jobs.POST_SYNC_HOOKS.append(deals.post_sync_hook)
    # v0.6: watchlist matching is deterministic and cheap - always runs
    import watchlists
    if watchlists.post_sync_hook not in jobs.POST_SYNC_HOOKS:
        jobs.POST_SYNC_HOOKS.append(watchlists.post_sync_hook)
    # v0.6: digest schedules ride the scheduler tick (cheap when idle)
    import digests
    if digests.enqueue_due not in jobs.TICK_HOOKS:
        jobs.TICK_HOOKS.append(digests.enqueue_due)
    # v0.7: discovery stays fresh after every sync - deterministic term
    # stats + question radar (no AI), and the entity pipeline (gazetteer
    # matching always; LLM discovery only when opted in)
    import discover
    if discover.post_sync_hook not in jobs.POST_SYNC_HOOKS:
        jobs.POST_SYNC_HOOKS.append(discover.post_sync_hook)
    if entities.post_sync_hook not in jobs.POST_SYNC_HOOKS:
        jobs.POST_SYNC_HOOKS.append(entities.post_sync_hook)
    _start_discover_backfill_if_needed()
    yield


app = FastAPI(title="Telegram Query", version=config.__version__,
              docs_url=None, redoc_url=None, openapi_url=None,
              lifespan=lifespan)

for router in (general.router, auth_api.router, archive.router,
               ai_api.router, groups.router, jobs_api.router, setup_api.router,
               scheduler_api.router, saved_api.router, bookmarks_api.router,
               exports_api.router, deals_api.router, research_api.router,
               monitor_api.router, faqs_api.router, digests_api.router,
               discover_api.router):
    app.include_router(router)


# ---------------------------------------------------------------------------
# Local-first request guard: only loopback / explicitly-configured hosts may
# talk to the API. Blocks other origins (DNS rebinding, cross-site form POSTs).
# ---------------------------------------------------------------------------

def _allowed_hosts() -> set[str]:
    hosts = {"localhost", "127.0.0.1", "::1", "testserver"}
    if config.settings.host and config.settings.host != "0.0.0.0":
        hosts.add(config.settings.host.lower())
    extra = os.environ.get("TG_ALLOWED_HOSTS", "")
    hosts.update(h.strip().lower() for h in extra.split(",") if h.strip())
    return hosts


def _host_token(raw: str) -> str:
    """'localhost:8000' -> 'localhost'; '[::1]:8000'/'[::1]' -> '::1'."""
    if raw.startswith("["):
        return raw[1:raw.index("]")] if "]" in raw else raw
    return raw.rsplit(":", 1)[0]


@app.middleware("http")
async def host_guard(request: Request, call_next):
    raw = (request.headers.get("host") or "").strip().lower()
    if _host_token(raw) not in _allowed_hosts():
        log.warning("blocked request with Host %r", raw)
        return JSONResponse(
            {"error": "This app only accepts requests addressed to the "
                      "local machine."},
            status_code=403)
    return await call_next(request)


@app.get("/")
def index():
    """Serve the built React app."""
    if (WEB_DIST / "index.html").exists():
        return FileResponse(WEB_DIST / "index.html")
    return JSONResponse(
        {"error": "Frontend build missing - run: cd web && npm install && npm run build"},
        status_code=500)


if (WEB_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"),
              name="assets")


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path, exc_info=exc)
    return JSONResponse({"error": "Internal server error - see the app logs."},
                        status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.settings.host, port=config.settings.port)
