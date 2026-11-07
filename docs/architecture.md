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
                   │  ├─ ai.py         ask (with explicit scope)   │
                   │  ├─ groups.py     track / dialogs              │
                   │  ├─ jobs.py       sync / stop / status         │
                   │  ├─ scheduler.py  auto-sync config             │
                   │  ├─ saved.py      saved searches               │
                   │  ├─ bookmarks.py  stars + private notes        │
                   │  ├─ exports.py    Markdown/JSON downloads      │
                   │  ├─ deals.py      deals workspace              │
                   │  ├─ research.py   briefs workspace             │
                   │  ├─ monitor.py    watchlists + alerts inbox    │
                   │  ├─ digests.py    digests + schedules          │
                   │  └─ faqs.py       FAQ review workflow           │
                   │                                              │
                   │  jobs.py  JobRunner (single-slot queue)       │
                   │  sync.py  Telethon sync + checkpoints         │
                   │  auth.py  Telegram login steps               │
                   │  scheduler.py  auto-sync loop (DB-persisted)  │
                   │  ai_tasks.py    shared AI task runner         │
                   │  deals.py / research.py / digests.py / faq.py │
                   │  watchlists.py  deterministic monitors         │
                   │  config.py  Settings from env / .env          │
                   └─────────────────┬─────────────────────────────┘
                                     │
                      ┌──────────────┴────────────────┐
                      │ SQLite (WAL) + FTS5            │
                      │ data/messages.db  (schema v5)  │
                      │ data/tg_session.session         │
                      └─────────────────────────────────┘
```

## Modules

| File | Role |
|---|---|
| `config.py` | Single `Settings` object; env parsing, aliases, path resolution, normalization level |
| `app.py` | Thin entry: routers, static serving, startup threads, post-sync + tick hook registration |
| `api/` | HTTP routers grouped by domain; each opens its own DB connection |
| `db.py` | Schema + versioned migrations (v5), upserts with **incremental FTS upkeep**, keyset-paginated browse, search (star/min-id filters), normalization, settings KV, verified `t.me` link builder |
| `sync.py` | Telethon CLI/web sync; checkpointed resumable backfills; `reply_to` capture; `CANCEL` event honored between messages |
| `auth.py` | Login steps (phone → code → 2FA); pending state kept in memory only |
| `jobs.py` | JobRunner: jobs run **one at a time** (the Telegram session must not be used concurrently); queue with dedupe + priority; stdout captured for the live log; `POST_SYNC_HOOKS` + `TICK_HOOKS` seams; reindex/extract/brief/digest/faq jobs |
| `scheduler.py` | Auto-sync: DB-persisted schedule (`app_settings`), 30s loop, catch-up after downtime, never overlaps a running sync |
| `ai.py` | Ask-AI: extract keywords → FTS → (retry) → grounded answer; explicit scope chips override model guesses |
| `ai_tasks.py` | Shared AI task layer: fence-tolerant parsing, schema validation with ONE repair attempt, provider retries with backoff+jitter, fingerprint result cache, per-task usage recording, versioned prompts, shared citation validation |
| `deals.py` | Deals pipeline: bilingual keyword net → batched schema-constrained extraction → strict identity merge (sources preserved) → evidence-derived status; per-chat watermark for incremental runs |
| `research.py` | Briefs: keyword retrieval + reply/neighbor context expansion → cited brief → versioned saves; deterministic staleness |
| `watchlists.py` | Deterministic keyword monitors over each sync's new messages; **never calls the AI** |
| `digests.py` | Period digests with deterministic theme hints; schedule due-check + fingerprint reuse |
| `faq.py` | Question detection + conservative clustering; drafted answers stay `candidate` until a human approves |
| `web/` | React + TypeScript source (Vite); production build committed to `web/dist/` |

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

**Search normalization.** `normalize_text` (level `extended`, default)
lowercases, strips Arabic diacritics/tatweel, unifies alef/ya/taa-marbuta
variants, folds Arabic-Indic digits, collapses chat elongation, folds
Arabizi digits inside Latin words (never multi-digit price/code runs),
and maps common Gulf dialect words to standard forms — at index AND
query time, so both sides always match. `standard` reproduces v0.3
exactly. Original message text is never modified.

**Deterministic-first monitoring.** Watchlists match normalized keywords
above a per-chat watermark with zero AI involvement; alerts dedupe per
watchlist+message (UNIQUE). Deals incremental extraction and digest
schedule checks ride the same seams (`POST_SYNC_HOOKS`, `TICK_HOOKS`) so
nothing scans the whole archive per run.

**Human gates.** FAQ answers are `candidate` until approved; new evidence
flags an approved answer for review instead of silently replacing it.
Extracted deals carry evidence-derived status (`active` without validity
evidence reads `unverified`) with confirm/dismiss/correct controls.

**Local-only posture.** No auth in-app; the default bind is `127.0.0.1`.
The docs and UI disclose exactly what leaves the machine (retrieved
excerpts, on request, to your chosen endpoint — see [privacy.md](privacy.md)).
