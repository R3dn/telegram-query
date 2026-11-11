# Security Review — Telegram Query v0.8.1 (+ v9 hardening)

Review date: 2026-11-10 · Scope: full backend (app, api/, feature
modules, sync), frontend (React/TS), configuration, deployment posture.
Method: line-level review of every input path, all SQL, all
provider-facing code, plus the secret-handling surface. Findings are
ranked and each states what is implemented vs. what is accepted risk.

## Threat model

**Deployment assumption (load-bearing):** a single trusted user runs
this app on their own machine; the browser talking to it is theirs.
The assets are (1) the complete message archive, (2) the Telegram
session file (account takeover = full account control), (3) AI/Telegram
API keys. **Adversaries:** web pages the user visits (drive-by/CSRF/
DNS-rebinding), local malware (out of scope — it already owns the
machine), and malicious content inside archived messages (prompt
injection into AI features).

## What protects the assets today (verified in code)

| Control | Where | Verified how |
|---|---|---|
| Loopback-only bind by default (`127.0.0.1`) | `config.py` | default + `HOST` docs |
| Host-allowlist middleware (DNS-rebinding / cross-site form defense) | `app.py:host_guard` | test suite (`test_hardening`) |
| No CORS headers anywhere — same-origin only | `app.py` | grep; browser SOP blocks cross-origin fetch |
| No secrets in responses: setup endpoints write-only, keys never echoed | `api/setup.py` | code + tests |
| Secrets never logged (`ai_provider_host` display only; keys redacted everywhere) | all modules | grep for `api_key` in log/print paths |
| `.env`, `*.session`, `data/`, `messages.db*` gitignored | `.gitignore` | `git check-ignore` |
| All SQL parameterized; f-strings only build `?`-placeholder lists or fixed literals | all `db`/`api` code | line review |
| Strict input patterns on wizard fields (blocks `.env` line injection) | `api/setup.py` pydantic patterns | code + tests |
| `config.update_env` rejects newlines in values | `config.py` | code |
| Markdown renderer escapes **all** HTML before adding markup (no XSS from AI answers) | `web/src/utils/markdown.ts` | unit tests |
| Highlight regexes escape user input (no ReDoS injection from query text) | `web/src/utils/format.ts` | unit tests |
| Generic 500s (`Internal server error - see the app logs`) — no stack/SQL leakage | `app.py:unhandled_error` | code |
| Exports contain no credentials or session data | `api/exports.py` | code |
| Prompt-injection hardening: system prompts frame message excerpts as DATA; backend **validates every `[n]` citation** against real retrieved rows and strips the rest | `ai.py`, `ai_tasks.validate_citations` | tests |
| Provider client timeout (90 s) — requests can't hang forever | `ai.py` | code |
| AI daily cap (`TGQ_AI_DAILY_CAP`, default off) available for cost abuse control | `ai_tasks` | tests |
| v9: provider concurrency bound (`TGQ_AI_MAX_CONCURRENCY`, default 4) | `ai.py`, `ai_tasks.py` | new test |
| v9: `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` on every response | `app.py` | middleware |
| v9: loud startup warning on non-loopback `HOST` | `app.py` | code |
| v9: CLI sync refuses to share the Telegram session with a running app (`--force` to override) | `sync.py` | new test |

## Findings & remediation status

### Accepted-by-design (local-first posture)

1. **No authentication on the API.** By design for localhost; the API
   serves the full archive to whoever can reach it. Controls in place:
   loopback default, host guard, warning on unsafe bind. **Required
   before any network exposure:** an authenticating reverse proxy
   (see the archived `docs/archive/PRODUCTION_DEPLOYMENT.md` — this is
   the gate, not optional).
2. **No rate limiting.** Same posture. The AI endpoint is additionally
   bounded by the concurrency slot; the daily cap exists when cost
   matters. A reverse proxy should rate-limit if exposed.
3. **`AI_BASE_URL` is operator-controlled SSRF surface** (the server
   will call any URL configured). The only person who can set it is the
   local operator; cross-origin browser abuse is blocked by the host
   guard (attacker cannot forge `Host: localhost` + no CORS). Accepted;
   documented. A same-origin-scripting compromise would already be
   game over for a localhost app.
4. **Session file is a bearer credential on disk.** It is gitignored
   and never leaves the machine; `log_out()` deletes it. File-system
   permissions are the user's OS-level concern (documented in the
   deployment guide).

### Fixed in this pass

5. **Shutdown-state leak (correctness/security-adjacent):** graceful
   shutdown previously left module-global cancel/stop flags set, which
   silently disabled later app instances in the same process — fixed
   with startup reset + shutdown cleanup (found via the test suite,
   pinned by it).
6. **Stale-version E2E assertion** could mask regressions in shipped
   metadata — fixed to compare against `config.__version__`.

### Low, documented

7. **`httpx` logs provider requests at INFO** (URL only, never the key).
   Noise, not a leak; noted for operators setting `LOG_LEVEL=WARNING`.
8. **`ai_temperature`/numeric env parsing** can raise at startup on
   malformed values — fail-fast is the intended behavior for config
   errors on a personal app; documented in `docs/configuration.md`.

## Pre-exposure checklist (mandatory gates)

1. Authenticating reverse proxy (TLS) in front; the app itself stays on
   `127.0.0.1`.
2. Set `TG_ALLOWED_HOSTS` to the public hostname only.
3. Rate-limit `/api/ask` and `/api/sync` at the proxy.
4. Consider `TGQ_AI_DAILY_CAP` to bound cost from any compromise.
5. Restrict OS file permissions on the data directory (session + DB).
6. Put backups (`scripts/backup_db.py`) on a schedule; they contain the
   full archive.

**Secrets in the browser:** the frontend bundle contains no secrets
(keys are backend-only; verified — the API client never receives or
sends credentials). Setup wizard input travels write-only to the
backend; nothing sensitive is read back.
