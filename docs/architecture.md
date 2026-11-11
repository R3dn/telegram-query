# Architecture

Local-first by design: one process, one SQLite database, one Telegram
session, zero external services.

```
┌────────────┐     ┌──────────────────────────────────────────────┐
│  Browser    │     │              python app.py                    │
│ React SPA   │────▶│  FastAPI  (api/ routers)                     │
│ (web/dist)  │ /api│  ├─ general.py    app state / health          │
└────────────┘     │  ├─ auth.py       phone/code/2FA login         │
                    │  ├─ archive.py    browse / search / message    │
                    │  │                 / conversation context     │
                    │  ├─ ai.py         ask (with explicit scope)   │
                    │  ├─ groups.py     track / dialogs              │
                    │  ├─ jobs.py       sync / stop / status         │
                    │  ├─ scheduler.py  auto-sync config             │
                    │  ├─ saved.py      saved searches               │
                    │  ├─ bookmarks.py  stars + private notes        │
                    │  ├─ exports.py    Markdown/JSON downloads      │
                    │  ├─ deals.py      deals workspace              │
                    │  ├─ decisions.py  decisions workspace         │
                    │  ├─ evidence.py   reverse-citation lookup      │
                    │  ├─ research.py   briefs workspace             │
                    │  ├─ monitor.py    watchlists + alerts inbox    │
                    │  ├─ digests.py    digests + schedules          │
                    │  ├─ faqs.py       FAQ review workflow           │
                    │  └─ discover.py   trending / stories / activity│
                    │                   questions / entities /        │
                    │                   topic timeline               │
                    │                                              │
                    │  jobs.py  JobRunner (single-slot queue)       │
                    │  sync.py  Telethon sync + checkpoints         │
                    │  auth.py  Telegram login steps               │
                    │  scheduler.py  auto-sync loop (DB-persisted)  │
                    │  ai_tasks.py    shared AI task runner         │
                    │                 (routing: extract|synth|embed)│
                    │  deals.py / decisions.py / research.py /      │
                    │                 digests.py / faq.py            │
                    │  watchlists.py  deterministic monitors         │
                    │  discover.py    term analytics / stories /     │
                    │                 questions / timeline          │
                    │  entities.py    gazetteer + mention matching  │
                    │  config.py  Settings from env / .env          │
                    └─────────────────┬─────────────────────────────┘
                                      │
                        ┌──────────────┴─────────────────┐
                        │ SQLite (WAL, synchronous=NORMAL) │
                        │ data/messages.db  (schema v9)     │
                        │  keyset index (date,chat,msg_id)  │
                        │  chat_sender + reply indexes (v9) │
                        │  FTS5 trigram external-content     │
                        │ data/tg_session.session            │
                        └────────────────────────────────┘
```

## Modules

| File | Role |
|---|---|
| `config.py` | Single `Settings` object; env parsing, aliases, path resolution, normalization level, model routing (`AI_MODEL_EXTRACT/SYNTH/EMBED` with `AI_MODEL` fallback), daily AI cap. v1.0: frozen-aware paths — source runs keep `<repo>/data`, packaged builds move mutable data to `%LOCALAPPDATA%\TelegramQuery` and the `.env` there; `reload_settings()` after migration |
| `desktop.py` | v1.0 desktop runtime for packaged builds: named-mutex single instance, legacy-archive migration hook, rotating file log, loopback-only Uvicorn in a worker thread, busy-port fallback (actual port discoverable via `runtime.json`), health-gated browser open (no blind sleeps), explicit quit (`POST /api/app/quit`) with graceful shutdown, native error dialogs pointing at the log |
| `migration.py` | v1.0 copy-based archive migration into the user data dir (never overwrites: backup, idempotent, interrupt-safe, SQLite backup-API restore, preserves session + settings) |
| `app.py` | Thin entry: routers, static serving (immutable hashed assets, v9 security headers), startup threads, graceful shutdown (v9: cancel running job, clean state), post-sync + tick hook registration, upgrade backfill jobs (reindex, discovery), non-loopback bind warning |
| `api/` | HTTP routers grouped by domain; each opens its own DB connection; `/api/health/ready` readiness (v9) |
| `db.py` | Schema + versioned migrations (v9: composite keyset index `(date,chat_id,msg_id)` with row-value cursors, `chat_sender`/`reply` indexes, one-time ANALYZE + post-sync `analyze_if_stale` maintenance), WAL + `synchronous=NORMAL`, fast-path upserts (FTS upkeep only when text changes), upserts with **incremental FTS upkeep**, keyset-paginated browse, rank-subquery search (filters before LIMIT, joins after), single-query round-robin `search_diverse`, settings KV, verified `t.me` link builder, conversation reconstruction |
| `sync.py` | Telethon CLI/web sync; checkpointed resumable backfills; `reply_to` capture; `CANCEL` event honored between messages |
| `auth.py` | Login steps (phone → code → 2FA); pending state kept in memory only |
| `jobs.py` | JobRunner: jobs run **one at a time** (the Telegram session must not be used concurrently); queue with dedupe + priority; stdout captured for the live log; `POST_SYNC_HOOKS` + `TICK_HOOKS` seams; reindex/extract/decisions/brief/digest/faq/discover jobs |
| `scheduler.py` | Auto-sync: DB-persisted schedule (`app_settings`), 30s loop, catch-up after downtime, never overlaps a running sync |
| `ai.py` | Ask-AI: extract keywords (extract model) → FTS (`search_diverse`, one query per attempt) → (retry) → grounded answer (synth model); explicit scope chips override model guesses; v9: process-cached provider client (rebuilt on settings change), bounded provider concurrency (`TGQ_AI_MAX_CONCURRENCY`), real token usage recording |
| `ai_tasks.py` | Shared AI task layer: model routing per task type, fence-tolerant parsing, schema validation with ONE repair attempt, provider retries with backoff+jitter, per-fingerprint result cache, per-task usage recording **with the model that served it**, daily request cap, versioned prompts, shared citation validation |
| `deals.py` | Deals pipeline: bilingual keyword net → batched schema-constrained extraction (extract model) → strict identity merge (sources preserved) → evidence-derived status; per-chat watermark for incremental runs |
| `decisions.py` | v0.8 decisions pipeline (same contract as deals): bilingual keyword net → batched schema-constrained extraction → strict identity merge (title+owner+due) → citations verified against the archive; evidence-derived status (`completed`/`cancelled` only from the message's words, past due → `overdue`, no evidence → `unverified`); per-chat watermark for incremental runs. v0.8.1 adds deterministic follow-up tracking: open decisions are checked after each sync for newer messages matching ≥ 2 title keywords (shared discovery stopwords), stored as per-decision follow-up citations above an advancing watermark — never AI, never a full-archive scan |
| `api/evidence.py` | Evidence Explorer: one read-only reverse-citation lookup — deals, decisions (source + follow-up), brief versions, digests, alerts, FAQ clusters (question/answer side), entity mentions, and the message's thread context (parent + direct replies) |
| `research.py` | Briefs: keyword retrieval + reply/neighbor context expansion → cited brief (synth model) → versioned saves; deterministic staleness |
| `watchlists.py` | Deterministic keyword monitors over each sync's new messages; **never calls the AI** |
| `digests.py` | Period digests with deterministic theme hints; schedule due-check + fingerprint reuse (synth model) |
| `faq.py` | Question detection (shared with the radar) + conservative clustering; drafted answers stay `candidate` until a human approves |
| `discover.py` | v0.7 discovery engine: incremental daily term counts (`term_daily`), deterministic burst-scored trending, cross-group story clustering, group activity aggregates (never per-member), unanswered-questions radar (watermark-incremental, auto-resolving, human-gated), and the AI topic timeline (synth model, citation-validated, cached) |
| `entities.py` | v0.7 entity gazetteer: deterministic seeds (deal vendors) + manual adds + opt-in LLM discovery (extract model, cached); deterministic mention matching over `text_norm`; never individual people |
| `web/` | React + TypeScript source (Vite); production build committed to `web/dist/`; v1.0 design system in `web/src/design/` (tokens, Lucide icon namespace, per-view CSS), bilingual UI (EN/AR + true RTL) in `web/src/i18n/` |

## Key decisions

**One Telegram job at a time.** The session is a SQLite file; concurrent
clients can corrupt it. The JobRunner serializes all jobs and streams each
job's stdout to the UI.

**Checkpointed backfills.** History walks (newest→oldest) write a
`backfill_floor` checkpoint every 500 messages. Stopping (or crashing)
keeps progress; the next sync resumes below the floor.

**Incremental FTS.** `messages_fts` is an external-content FTS5 table.
`upsert_message` deletes/re-adds only the touched row's index entry —
no periodic rebuilds. A one-time `reindex` job rewrites `text_norm` when
normalization rules change (queued automatically on upgrade).

**Grounded AI with a shared task layer.** All structured AI features go
through `ai_tasks.run_json_task`: the provider is a capability, not the
engine — no JSON-mode assumptions, validation against app schemas, one
repair attempt, honest failure otherwise, results cached by source
fingerprint, and every stored output records its prompt version + model.
Citations (`[n]`) are validated on the backend against the real retrieved
set; unresolvable markers are stripped and reported.

**Model routing (v0.7).** `AI_MODEL_EXTRACT` serves cheap structured
tasks (deals, decisions, entities, keyword extraction), `AI_MODEL_SYNTH` serves
answers/briefs/digests/FAQ answers/timelines, `AI_MODEL_EMBED` is
reserved for the benchmark-gated hybrid retrieval. Every role falls
back to `AI_MODEL` — routing is optional, provider-agnostic, and a
`TGQ_AI_DAILY_CAP` guards the daily budget with honest errors while
deterministic features keep working.

**Search normalization.** `normalize_text` (level `extended`, default)
lowercases, strips Arabic diacritics/tatweel, unifies alef/ya/taa-marbuta
variants, folds Arabic-Indic digits, collapses chat elongation, folds
Arabizi digits inside Latin words (never multi-digit price/code runs),
and maps common Gulf dialect words to standard forms — at index AND
query time, so both sides always match. `standard` reproduces v0.3
exactly. Original message text is never modified.

**Deterministic-first monitoring and discovery.** Watchlists match
normalized keywords above a per-chat watermark with zero AI involvement.
Discovery (v0.7) follows the same doctrine: term stats, trending burst
scoring, stories, activity, and the question radar are pure
SQL/Python over stored `text_norm` and cost nothing; the only AI
surfaces are the opt-in entity gazetteer growth and the cited topic
timeline, both fingerprint-cached. Decision follow-up tracking (v0.8.1)
joins them: pure keyword matching over `text_norm`, incremental above
each decision's watermark. All incremental work rides
`POST_SYNC_HOOKS`/`TICK_HOOKS` — nothing scans the whole archive per
run. Entity tracking covers brands/products/orgs/places/events and
**never individual people** — no member analytics exists in this
product.

**Human gates.** FAQ answers are `candidate` until approved; new evidence
flags an approved answer for review instead of silently replacing it.
Extracted deals carry evidence-derived status (`active` without validity
evidence reads `unverified`) with confirm/dismiss/correct controls.
Decisions follow the same doctrine: `completed`/`cancelled` come only
from the message's own words, a past due date reads `overdue`, and a
record without evidence reads `unverified` — the model's own judgment is
kept in a separate column so extraction can never invent commitment.
Question statuses are human-controlled and never overwritten by rescans.
The Evidence Explorer (v0.8.1) closes the loop from the other side:
every citation table is queryable in reverse, so any message can prove
what was built on top of it.

**Local-only posture.** No auth in-app; the default bind is `127.0.0.1`
(a non-loopback bind logs a loud warning). The docs and UI disclose
exactly what leaves the machine (retrieved excerpts, on request, to
your chosen endpoint — see [privacy.md](privacy.md)).

**v9 engineering pass** (2026-11): a full audit, measured baseline,
and targeted optimization round live in
[docs/engineering/](engineering/) — the short version of what changed
architecturally: the archive's hot read paths are index-satisfiable by
construction (composite keyset index + row-value cursors, sender/reply
indexes, planner statistics refreshed on a doubling threshold after
syncs), search ranks in a subquery with all filters applied before the
LIMIT and joins only afterward, the AI provider layer is a single
cached client with bounded concurrency and real token accounting,
liveness (`/api/health`) and readiness (`/api/health/ready`) are
separate, shutdown is graceful, and `scripts/benchmark.py` +
`scripts/backup_db.py` make performance and backups repeatable
operations rather than hopes.

## Desktop packaging (v1.0)

The Windows product is one process, same as source runs — packaging
only changes *where files live* and *who owns the lifecycle*:

```
TelegramQuery-Setup-x64.exe        Burn bootstrapper (license UI, chains
                                   the MSI; the only ARP entry)
  └─ TelegramQuery-x64.msi         perMachine MSI, MajorUpgrade, both
     └─ TelegramQuery/             PyInstaller onedir (windowed, no
        ├─ TelegramQuery.exe         console): desktop.py entry, app +
        └─ _internal/                api/ + web/dist bundled read-only
```

- **One pipeline, two artifacts**: `scripts/build_windows.py` builds the
  frontend (`scripts/build_frontend.py`, version-checked against
  `config.__version__`), freezes with the spec in
  `packaging/windows/pyinstaller/`, harvests with WiX `heat`, links the
  MSI and the Burn bundle from the same `TelegramQuery.wxs` definition,
  and writes `dist/release/` with SHA-256 checksums. CI runs it on
  `windows-2022` and uploads the artifacts.
- **Upgrade identity** comes from fixed `UpgradeCode` GUIDs in the build
  script (never regenerated); `ProductCode` changes per build, so
  installing a new MSI over an old one is a MajorUpgrade — files
  replaced, data untouched, downgrades refused.
- **Data placement** is the packaged/source split in `config.py`:
  mutable data (SQLite archive, Telegram session, `.env`, logs) lives in
  `%LOCALAPPDATA%\TelegramQuery`, never inside Program Files, and
  survives uninstall by design. The explicit erase
  (`POST /api/data/erase` + Settings UI) is the only in-app way to
  remove it.
- **Security posture is unchanged**: the desktop runtime forces a
  loopback bind, the API never returns secrets to the frontend, and
  the bootstrapper runs the same MSI a script would (`msiexec /i …
  /qn`) — no service, no auto-start, no background anything.
- **Honest lifecycle**: health-gated browser open, discoverable port
  (`runtime.json`), single-instance mutex, graceful shutdown through
  the same FastAPI lifespan as source runs, and crash visibility via a
  native dialog + rotating log instead of a silent exit.
