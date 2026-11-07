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
from api import ai as ai_api
from api import archive, general, groups, jobs
from api import auth as auth_api
from api import setup as setup_api

logging.basicConfig(
    level=config.settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("tgq")

WEB_DIST = config.APP_ROOT / "web" / "dist"

db.init_db()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # check the Telegram session in the background (cheap, cached)
    threading.Thread(target=lambda: tg_auth.run(tg_auth.refresh_auth_state()),
                     daemon=True).start()
    yield


app = FastAPI(title="Telegram Query", version=config.__version__,
              docs_url=None, redoc_url=None, openapi_url=None,
              lifespan=lifespan)

for router in (general.router, auth_api.router, archive.router,
               ai_api.router, groups.router, jobs.router, setup_api.router):
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
