# Architecture Audit — Telegram Query v0.8.1

Audit date: 2026-11-10 · Method: full read of every backend module, all API
routers, the React frontend (App/store/Feed/client), tests, and scripts.
Claims below cite file/line evidence. Performance claims that need data are
marked **[measure]** and are quantified in `PERFORMANCE_BASELINE.md`.

---

## 1. Current architecture (verified in code)

```
Browser (React 18 SPA, web/dist served by backend)
   │  fetch() JSON, same-origin
   ▼
FastAPI (uvicorn, single process)  ................ app.py
   ├─ 19 routers in api/ (archive, ai, groups, jobs, auth, setup,
   │  scheduler, saved, bookmarks, exports, deals, decisions, evidence,
   │  research, monitor, faqs, digests, discover, general)
   │    · ALL handlers are `def` (sync) → Starlette runs them in the
   │      anyio threadpool (default capacity 40 threads)
   │    · every handler opens its own sqlite3 connection (api/__init__.open_db)
   ├─ host-guard middleware (loopback allowlist, DNS-rebinding defense)
   ├─ lifespan: auth-state thread, scheduler thread, upgrade backfill jobs,
   │  POST_SYNC_HOOKS + TICK_HOOKS registration
   │
   ├─ jobs.JobRunner ........................ single-slot job queue (thread)
   │    · one job at a time (Telethon session = one SQLite file)
   │    · stdout Tee'd into a live log polled by the UI
   │    · sync → asyncio.run(sync.run) → Telethon MTProto
   │    · post-sync hooks: watchlists, deals, decisions, discover, entities
   │
   ├─ scheduler.run_loop ...................... 30s daemon thread; DB-persisted
   │    · due-sync firing + TICK_HOOKS (digest schedules)
   │
   ├─ ai.ask / ai_tasks.run_json_task ......... OpenAI-compatible provider
   │    · ai.ask: keywords → FTS → (≤2 retries) → grounded answer
   │    · ai_tasks: retry+backoff, schema validation, one repair, fingerprint
   │      cache, usage accounting, daily cap
   │
   ▼
SQLite (WAL, busy_timeout 20s, foreign_keys ON) .. db.py
   · 16 tables + FTS5 external-content trigram index (messages_fts)
   · schema v8; versioned additive-only migrations (_migrate)
   · keyset pagination for browse; FTS bm25 ranking for search
```

**Data flow (sync):** Telethon → `sync.sync_chat` → `db.upsert_message`
(incremental FTS upkeep) → commit every 200 msgs → per-chat checkpoints
(`backfill_floor`) → `POST_SYNC_HOOKS` (watchlists/deals/decisions/discover/
entities, all watermark-incremental) → UI refresh via job polling.

**Data flow (read):** Browser → router → per-request connection → SQL
(keyset browse / FTS search) → JSON. AI flow adds provider calls from the
request thread (threadpool).

## 2. Component responsibilities (verified)

| Component | Responsibility | Coupling / notes |
|---|---|---|
| `config.py` | env → `Settings`; `.env` writer with hot reload | `db.DB_PATH` bound at import (OK: DB path not wizard-settable) |
| `db.py` (874 L) | schema, migrations, normalization, search/browse, stats, conversation | single God-module but cohesive; no repo layer (OK at this size — see §6) |
| `sync.py` | Telethon ingest, checkpointed backfill, flood-wait handling | `CANCEL` global event; client per sync run |
| `auth.py` | phone/code/2FA steps; pending state memory-only | shares session w/ jobs (409 guard in api/auth.py) |
| `jobs.py` | serialized job runner, dedupe, live log | `sys.stdout` swap is process-wide (see §5.6) |
| `scheduler.py` | DB-persisted auto-sync cadence | re-reads state per tick — good |
| `ai.py` | ask pipeline (extract→search→answer) | client per call; N+1 diverse search (§5.2) |
| `ai_tasks.py` | shared provider runner, cache, usage, cap | retries/backoff only here (not in ai.ask) |
| `deals/decisions/digests/research/faq/discover/entities/watchlists` | feature pipelines, all watermark-incremental | good boundaries; prompts versioned |
| `api/*` | thin routers, parameterized SQL only | no service layer (fine at this scale) |
| `web/src/state/store.tsx` | global context store; feed, jobs polling, filters | single context — see §7 |

## 3. Critical execution paths

1. **Browse feed** `/api/messages` → `db.browse` — keyset pagination, correct
   composite cursor; `ORDER BY date,chat_id,msg_id` over
   `idx_messages_date` + sort. **[measure]** plan/latency at 100k–500k rows.
2. **Search** `/api/search` → `db.search` — FTS5 trigram MATCH, bm25 rank,
   filters post-join. **[measure]**.
3. **AI ask** `/api/ask` → `ai.ask_db` → up to 3 provider calls (90 s timeout
   each) + FTS searches in the request thread. Threadpool occupancy is the
   scalability ceiling (§5.1).
4. **Sync ingestion** `run_sync_job` → per-message `upsert_message`
   (1 SELECT + up to 3 writes) with commit every 200 msgs. **[measure]** msg/s.
5. **UI polling** `/api/job/status` (1.2 s while running), `/api/app/state`,
   `/api/groups` on completion → `db.stats` + groups aggregate each time.

## 4. What is already good (kept, not rewritten)

- **WAL + busy_timeout 20 s + foreign_keys ON** on every connection
  (db.py:543-547); per-request connections — the correct SQLite pattern.
- **Keyset pagination** in `browse` (db.py:782-848) — no OFFSET scans.
- **Incremental FTS upkeep** per row (db.py:650-680) — no full rebuilds.
- **Watermark-incremental post-sync pipelines** everywhere — no per-run full
  archive scans (verified in watchlists/deals/decisions/discover/entities).
- **Checkpointed, resumable, idempotent backfills**; flood-wait handling;
  one dead group never aborts a sync (sync.py:147-160).
- **Single-slot job runner** — the Telethon session is never used
  concurrently; dedupe prevents queued duplicates.
- **Provider failure isolation** (`ai_tasks.TaskError`), schema-validated
  JSON with one repair, fingerprint cache, daily cap, usage accounting.
- **Parameterized SQL everywhere** — no string interpolation of user input
  (f-strings only build `?`-placeholder lists / fixed literals; verified).
- **Secrets hygiene**: setup endpoints write-only; keys never echoed or
  logged; `.env`, `*.session`, `data/` all gitignored (verified).
- **XSS-safe frontend**: markdown renderer escapes all HTML first
  (web/src/utils/markdown.ts:8-12); highlight regexes escape input
  (format.ts:34-36).
- **Deterministic-first features** (watchlists/discovery) work with no AI.

## 5. Findings

Priorities: **P0** security/data-loss · **P1** perf/architecture ·
**P2** operability/extensibility · **P3** minor/DX.

### 5.1 Concurrency & execution model

- **[P1] Threadpool ceiling under concurrent load.** All handlers are sync
  `def` → anyio threadpool (40). An `/api/ask` can legally occupy a thread
  for up to ~90 s × 3 provider calls; 40 concurrent asks would starve every
  other endpoint including `/api/job/status`. No concurrency limit protects
  expensive operations. **Fix: cheap in-process semaphore for provider
  calls + document limits. [measure] concurrent behavior first.**
- **[P2] Graceful shutdown is absent.** `lifespan` has no shutdown path; a
  running sync is killed mid-flight (checkpoints make it resumable — by
  design), but the job thread and scheduler thread die abruptly with no
  CANCEL signal and no queue flush. Queued-but-not-started jobs are lost
  (documented limitation, README).
- **[P2] `jobs._run` swaps `sys.stdout` process-wide** (jobs.py:86-87).
  Serialised jobs make this safe for job-vs-job, but prints from other
  threads (scheduler ticks, hooks) during a job are captured into that
  job's UI log — cosmetic cross-contamination; logging (stderr) unaffected.

### 5.2 Database access

- **[P1] `db.browse` selects `m.text_norm` on every page** (db.py:794) and
  ships it in every `/api/messages` response. The frontend never uses it
  (verified across web/src). Roughly doubles browse payload bytes.
- **[P1] `db.senders` = full-table `GROUP BY sender_name` with no index**
  (db.py:851-862). O(N) per call; the store calls it on every group-selection
  change (store.tsx:171-182). **[measure]** at 100k+ rows.
- **[P1] `api/groups` aggregates `COUNT/MAX` over the whole messages table
  per call** (api/archive.py:33-41) — O(N); called after every job
  completion. **[measure]**.
- **[P1] `db.stats` runs 4 aggregate queries per call** (db.py:953-969);
  `/api/app/state` and `/api/stats` both hit it; also called after every
  job completion. **[measure]**.
- **[P1] Ingestion write path:** `upsert_message` = 1 SELECT + 1 upsert +
  1 FTS insert (+1 FTS delete when editing) per message (db.py:650-680);
  commits every 200 messages. SQLite default `synchronous=FULL` persists
  even under WAL; `synchronous=NORMAL` is the standard WAL companion and is
  crash-safe for this app's semantics (checkpoints + idempotent re-fetch).
  **[measure]** ingestion msg/s before/after.
- **[P1] `ai._search_diverse` is an N+1 FTS round-robin** (ai.py:133-159):
  one full FTS query per tracked chat × up to 3 attempts. With 20 tracked
  groups that's 60 FTS queries per ask. Can be one query with per-chat
  fairness applied in SQL (window function) or in Python over a single
  result set.
- **[P1] `discover.trending` runs one FTS query per returned term** for the
  cosmetic sample (discover.py:210-216) — up to 20 extra FTS queries per
  Discover view. Could reuse the already-computed window rows or run a
  single batched query. **[measure]**.
- **[P2] `export_deals` / `export_decisions` use per-row source queries**
  (api/exports.py:170-182, 236-243) and unbounded `SELECT *` — N+1 pattern
  bounded only by row counts. Same file: `export_ai_answer` re-fetches up to
  200 sources one-by-one (exports.py:122-139).
- **[P3] `db.search` calls `normalize_text` twice per phrase**
  (db.py:731-732).
- **Positive:** no OFFSET pagination; no SELECT-all-loops over messages in
  request paths; migration system is additive and versioned; FKs enforced.

### 5.3 Telethon / sync

- Solid checkpoint design. Two gaps:
  - **[P2] No cross-process ownership guard.** Running `python sync.py`
    while the server is running shares the session file from another
    process. SQLite protects the DB, but Telethon session use from two
    processes can trigger Telegram-side auth resets; a lockfile (or at
    least a warning) would make the constraint explicit. Documented today
    only in the code header.
  - **[P2] `sync_chat`'s `except Exception: print(f"  error: {e}")`
    (sync.py:239-240) swallows job-visible failure state** — a failed sync
    still updates `last_synced` and reports success to the scheduler
    (`last_done.ok` stays True). The scheduler's `last_success` then lies.
- **[P3] `iter_with_flood_retry` prints to stdout on flood waits — fine
  (job log), but `print` in `run_backfill` makes ingestion latency
  dependent on stdout capture overhead — negligible, ignore.**

### 5.4 AI integration

- **[P1] `ai.get_client()` builds a new `OpenAI` client (new httpx pool) per
  ask** (ai.py:70-75), and `ai_tasks._call_with_retry` re-creates it per
  attempt (ai_tasks.py:111). Connection/TLS setup is repeated per request.
  Fix: process-level cached client keyed on (base_url, api_key), invalidated
  by `config.update_env`. **[measure]** with the mock server (isolates
  connection-setup cost).
- **[P2] `ai.ask` has no provider-level retry/backoff** (ai.py:78-85) —
  unlike `ai_tasks`, one transient network error fails the whole ask.
- **[P2] `ai.ask` records usage with `tokens=None`** even when the provider
  reports usage (ai.py:299-310) — cost visibility gap for the most-used AI
  path. `_chat` discards `resp.usage`.
- **[P3] No streaming for long answers** — a full answer arrives after the
  provider finishes; acceptable for this product, note only.

### 5.5 Configuration, security, observability

- **[P2] Readiness vs liveness:** `/api/health` returns OK without touching
  the DB. A readiness check that verifies the DB (and reports degraded,
  not failed, when optional AI/Telegram are down) is required for sane
  process supervision.
- **[P2] Non-loopback bind has no guardrail.** `HOST=0.0.0.0` silently
  exposes a no-auth API that serves the full archive. A startup warning +
  docs is the minimum; nothing should break existing usage.
- **[P2] No request-level logging** (only job stdout + exceptions). No
  correlation IDs. For a local app, job-level logs suffice, but AI request
  failures/latency are invisible in logs (ai.py never logs).
- **[Security notes, verified]**: SQL fully parameterized; host allowlist
  blocks DNS-rebinding; setup endpoints validate strict patterns (no .env
  injection; config.update_env rejects newlines); AI prompt-injection is
  mitigated by system-prompt DATA framing + backend citation validation
  (messages can never inject a citation that doesn't index a real row);
  SSRF: `AI_BASE_URL` is user-controlled and the server will call it — the
  user is the local operator, and cross-origin browser abuse is blocked by
  the host guard; risk accepted and documented (SECURITY_REVIEW.md).
  Exports contain no secrets. `rate limiting` — none; acceptable on
  loopback, required before any exposure (documented).
- **[P3] `requirements.txt` unpinned ranges; installed `openai` is 3.x
  while the floor is `>=1.50`** — drift is already happening. Add honest
  upper bounds (e.g. `openai>=1.50,<4`) after the suite passes on 3.x.

### 5.6 Frontend (React)

- **[P2] No request cancellation.** Search/browse/filter changes fire
  sequentially-numbered requests (`loadSeq` guards state application,
  store.tsx:222-274) but stale in-flight requests are never aborted — they
  still consume a threadpool thread and serialize JSON that is then thrown
  away. `AbortController` + backend honoring cancellation closes the loop.
- **[P2] Senders fetched on every selection change** (store.tsx:171-182)
  amplifies the `db.senders` O(N) query (§5.2). Debounce/caching or a
  cheaper backend fixes it.
- **[P3] 3000-card soft DOM cap without virtualization** (Feed.tsx:110-119,
  206-215) — bounded and deliberate; revisit only if profiling shows jank.
- **[P3] Single 299.89 kB JS bundle (84.92 kB gzip), no route-level
  splitting.** All views are imported eagerly (App.tsx:4-23). Served from
  localhost, first-load impact is minimal; re-evaluate only if the bundle
  grows. **[measure]** initial load once in a browser.
- **Positive:** job polling stops when idle; toasts/errors have explicit
  states; no state-management library needed (context is fine at this size);
  TypeScript strict (tsconfig verified in build).

### 5.7 Testing & quality gates

- 222 backend tests + 44 frontend tests, all green; ruff clean; `tsc`
  strict build clean (2026-11-10 run).
- **[P2] No coverage of:** concurrent request behavior, `/api/health`
  degradation, graceful shutdown, ingestion performance regression,
  benchmark harness. Migration tests exist (test_migration.py).
- E2E script exists (scripts/e2e_test.py) and covers the main journey with
  a mock provider; it is not part of pytest (separate process model).

## 6. Architectural risks & technical debt

1. **`db.py` is a 874-line God module** (schema + migrations + normalization
   + queries). Still cohesive and well-tested; splitting is *not* justified
   yet — but new table domains should go to their own modules (deals/
   decisions already do). Rule: stop growing it.
2. **No service/repository boundary** between routers and SQL. At 19 routers
   this is fine; the feature modules already act as the service layer.
   Introduce repositories only when a second consumer of the same queries
   appears.
3. **In-memory job queue** — restart loses queued jobs (known, documented).
   A `jobs` table would fix it; P2, deferred with the product's own v0.10
   plan (ROADMAP) rather than a speculative rewrite.
4. **`sys.stdout` capture** (§5.1) couples job logging to print — acceptable,
   documented; do not extend the pattern to new code.
5. **Two AI call paths** (`ai._chat` vs `ai_tasks._call_with_retry`) — the
   ask pipeline bypasses the shared retry/usage layer. Consolidating ai.py
   onto ai_tasks primitives removes duplicated business logic (engineering
   rule: duplicate logic is debt).

## 7. Improvement priorities (ranked; measured in baseline doc)

| # | Priority | Item | Expected impact | Effort |
|---|---|---|---|---|
| 1 | P1 | SQLite pragma tuning (`synchronous=NORMAL`, cache_size, mmap) + ingestion statement reduction | ingest msg/s ↑ | S |
| 2 | P1 | Drop `text_norm` from browse payload | ~2× smaller feed pages | S |
| 3 | P1 | Index/aggregate strategy for `senders`, `groups`, `stats` hot paths | latency ↓ on every UI refresh | S/M |
| 4 | P1 | Cached AI client + single-query diverse search | ask latency ↓, N+1 gone | S |
| 5 | P1 | Provider concurrency guard (semaphore) + ai.ask retries/usage via ai_tasks | reliability + fairness | S |
| 6 | P2 | Readiness endpoint + startup warning on non-loopback bind | operability | S |
| 7 | P2 | Static asset cache headers | repeat-load speed | S |
| 8 | P2 | Frontend AbortController + senders debounce | fewer wasted requests | S |
| 9 | P2 | Backup script + DB ops runbook | data safety | S |
| 10 | P2 | Sync failure propagation (don't mark failed syncs OK) | reliability truth | S |
| 11 | P3 | Bundle/inline micro-opts (normalize once, exports batching) | minor | S |

**Explicitly not doing (over-engineering guards):** no ORM, no PostgreSQL,
no task queue, no frontend state library, no route splitting (measured
bundle is small), no multi-worker uvicorn (the single-process constraint is
load-bearing: Telethon session + in-process job runner + scheduler).
