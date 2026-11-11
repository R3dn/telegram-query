# Production Deployment — Telegram Query

> **Archived 2026-11-12 — historical reference.** Telegram Query now
> releases desktop-only (decision 0010,
> [docs/decisions/README.md](../decisions/README.md)): the loopback
> server is an embedded implementation detail of the desktop runtime,
> never a deployment surface. This pre-desktop runbook is kept for
> historical reference only.

Target: a single-user, self-hosted archive on a machine you control
(laptop, desktop, small home server). The design constraints below are
**load-bearing** — violating them breaks data or the Telegram session.

## 1. The single-process constraint (read first)

The app is deliberately **one process**:

- The Telethon session is one SQLite file; two clients on it can
  invalidate the session or corrupt it.
- The job runner, auto-sync scheduler, and post-sync hooks
  (watchlists/deals/decisions/discovery/entities/ANALYZE) all live
  in-process and are coordinated by a single-slot queue.

Therefore:

- **Never** run `uvicorn --workers N` with N > 1.
- **Never** run two `python app.py` instances against the same
  `TG_DATA_DIR` (the second bind fails; don't work around it).
- `python sync.py` refuses to run while the app is serving (v9 guard);
  `--force` overrides at your own risk.

Scale-out is not a feature of this product. A second Telegram account
or a second archive = a second installation with its own
`TG_DATA_DIR` (see `docs/decisions/`).

## 2. Requirements

- Python 3.10+ (3.13 tested), pip.
- Node is **not** needed at runtime (frontend build committed under
  `web/dist/`).
- Disk: the SQLite archive grows ~0.5 KB/message (500 k messages ≈
  290 MB with indexes). Keep free space for WAL + backups.

```bash
pip install -r requirements.txt
python app.py                 # -> http://127.0.0.1:8000
```

First run: the wizard collects Telegram API credentials, logs in,
selects groups, and optionally configures an AI provider. Everything
lands in `.env` + `data/`.

## 3. Configuration (all env / `.env`; full table in docs/configuration.md)

| Variable | Default | Production notes |
|---|---|---|
| `HOST` | `127.0.0.1` | **keep loopback** unless behind an auth proxy |
| `PORT` | `8000` | |
| `TG_DATA_DIR` | `<app>/data` | put persistent storage here |
| `TG_DB_PATH` / `TG_SESSION_PATH` | under data dir | point at persistent volumes |
| `LOG_LEVEL` | `INFO` | `WARNING` silences provider-request noise |
| `TG_ALLOWED_HOSTS` | — | comma-separated extra Host values (when proxied) |
| `TGQ_AI_DAILY_CAP` | `0` (off) | set to bound AI cost |
| `TGQ_AI_MAX_CONCURRENCY` | `4` | provider calls in flight |
| `SYNC_DAYS` | `3` | edit re-scan window |

Fail-fast behavior: malformed numeric env values (e.g. `PORT=abc`)
abort at startup with the offending key — intended for a personal app.

## 4. Process supervision

The app is a plain uvicorn process; supervise it with whatever your OS
gives you.

**systemd** (Linux):

```ini
[Unit]
Description=Telegram Query
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/telegram-query
Environment=TG_DATA_DIR=/var/lib/telegram-query
ExecStart=/opt/telegram-query/.venv/bin/python app.py
Restart=on-failure
RestartSec=5
# hardening: the app needs its data dir only
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/lib/telegram-query /opt/telegram-query

[Install]
WantedBy=default.target
```

**Windows:** run `python app.py` from Task Scheduler at logon, or keep
a terminal open. NSSM/service wrappers work fine — supervise the
process, nothing else.

Graceful shutdown: the app cancels the running job at its next
checkpoint (≤5 s wait), then exits. SIGTERM/SIGINT both work. A hard
kill is also safe: backfills are checkpointed; a killed sync resumes.

**Do not** use `--reload` in production.

## 5. Health checks

- **Liveness** — `GET /api/health` → `200 {"ok": true, ...}`. Touches
  nothing; use for "is the process up".
- **Readiness** — `GET /api/health/ready` → `200` when the archive DB
  answers a trivial query; `503` otherwise. Optional dependencies
  (Telegram auth, AI provider) are **reported but never fail readiness**
  — a dead provider must not make a supervisor kill the app.

Wire liveness to the supervisor's restart rule, readiness to a proxy's
upstream probe.

## 6. Reverse proxy (only if you must expose it)

Keep the app on `127.0.0.1:8000` and put an **authenticating** proxy in
front (oauth2-authelia-basic-auth-nginx, Caddy with basic auth, etc.):

- Terminate TLS at the proxy.
- Forward to `127.0.0.1:8000` with `Host` set to the public hostname
  and that hostname listed in `TG_ALLOWED_HOSTS`.
- Rate-limit `/api/ask` and `/api/sync`.
- The app's own security headers (`nosniff`, `DENY` framing,
  `no-referrer`) are set on every response; add HSTS/CSP at the proxy.

Without the auth proxy, **do not expose this app** — it serves your
complete archive with no authentication.

## 7. Static assets

`web/dist/` is committed; the app serves it. Hashed asset URLs get
`Cache-Control: immutable` (1 year); `index.html` is `no-cache` so new
builds are picked up immediately. To deploy a rebuilt frontend:
`cd web && npm install && npm run build` (build output is what the
backend serves — no Node needed afterward).

## 8. Backups (see DATABASE_OPERATIONS.md for the full runbook)

```bash
python scripts/backup_db.py --keep 14        # online, consistent snapshot
```

Schedule daily; a cron of the above with `--keep` is the whole policy.
Backups contain the full archive — store them accordingly.

## 9. Monitoring & logs

- Job logs stream to the UI and stdout (job progress, flood waits,
  per-chat errors, hook failures).
- Unhandled errors are logged with stack traces to stderr; responses
  stay generic.
- Provider requests log their URL at INFO (no key, no content).
- Watch: `data/messages.db` growth, WAL size, `last_synced` freshness
  (visible in Settings → scheduler), `pending_backfills` in `/api/stats`.

## 10. Startup/shutdown sequence (what actually happens)

1. `db.init_db()` → schema + migrations (v9: new indexes, ANALYZE once).
2. Lifespan: cancel/stop flags **reset**, auth check thread, scheduler
   thread, post-sync/tick hooks registered, upgrade backfills queued,
   non-loopback HOST warning if applicable.
3. Serve.
4. Shutdown (SIGINT/SIGTERM): CANCEL to the running job → ≤5 s wait →
   scheduler stopped → module flags cleared (next instance starts clean).

## 11. Common operational tasks

| Task | Command |
|---|---|
| Trigger a sync | UI → Jobs, or `POST /api/sync` |
| Stop a running job | UI, or `POST /api/job/stop` (checkpoints preserved) |
| Full re-fetch of a group | UI → untrack (keep) → track, or `python sync.py --track <id>` (app must not be running, or use the UI) |
| Re-normalize archive after a normalization change | Settings → Reindex (visible job, resumable) |
| Rebuild discovery layer | Discover view → rebuild |
| Backup | `python scripts/backup_db.py` |
| Integrity check | `python - <<'PY'` … `PRAGMA integrity_check` (see DATABASE_OPERATIONS.md) |
