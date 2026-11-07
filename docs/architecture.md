# Architecture

Local-first by design: one process, one SQLite database, one Telegram
session, zero external services.

```
┌────────────┐     ┌───────────────────────────────────────────┐
│  Browser    │     │              python app.py                │
│ React SPA   │────▶│  FastAPI  (api/ routers)                 │
│ (web/dist)  │ /api│  ├─ general.py   app state / health      │
└────────────┘     │  ├─ auth.py      phone/code/2FA login     │
                   │  ├─ archive.py   browse / search / groups │
                   │  ├─ ai.py        ask                      │
                   │  ├─ groups.py    track / dialogs          │
                   │  └─ jobs.py      sync / stop / status     │
                   │                                           │
                   │  jobs.py  JobRunner (single-slot queue)   │
                   │  sync.py  Telethon sync + checkpoints     │
                   │  auth.py  Telegram login steps            │
                   │  config.py  Settings from env / .env      │
                   └──────────────┬────────────────────────────┘
                                  │
                    ┌─────────────┴────────────┐
                    │ SQLite (WAL) + FTS5       │
                    │ data/messages.db          │
                    │ data/tg_session.session   │
                    └──────────────────────────┘
```

## Modules

| File | Role |
|---|---|
| `config.py` | Single `Settings` object; env parsing, aliases, path resolution |
| `app.py` | Thin entry: routers, static serving, startup auth probe |
| `api/` | HTTP routers grouped by domain; each opens its own DB connection |
| `db.py` | Schema + versioned migrations, upserts with **incremental FTS upkeep**, keyset-paginated browse, search, senders, stats |
| `sync.py` | Telethon CLI/web sync; checkpointed resumable backfills; `CANCEL` event honored between messages |
| `auth.py` | Login steps (phone → code → 2FA); pending state kept in memory only |
| `jobs.py` | JobRunner: jobs run **one at a time** (the Telegram session must not be used concurrently); queue with dedupe + priority; stdout captured for the live log |
| `ai.py` | Extract keywords → FTS → (retry) → grounded answer; balanced per-group retrieval; recent-messages fallback |
| `web/` | React + TypeScript source (Vite); production build committed to `web/dist/` |

## Key decisions

**One Telegram job at a time.** The session is a SQLite file; concurrent
clients can corrupt it. The JobRunner serializes sync/track/listing/login
and streams each job's stdout to the UI.

**Checkpointed backfills.** History walks (newest→oldest) write a
`backfill_floor` checkpoint every 500 messages. Stopping (or crashing)
keeps progress; the next sync resumes below the floor. The floor doubles
as "backfill pending" state surfaced in the UI.

**Incremental FTS.** `messages_fts` is an external-content FTS5 table.
`upsert_message` deletes/re-adds only the touched row's index entry —
no periodic rebuilds (an earlier design rebuilt the whole index every
500 messages, which was O(n²) and held write locks for seconds).

**Grounded AI.** The pipeline is extract → search → retry → answer. The
retriever round-robins hits across groups so a huge group can't crowd out
smaller ones; the answer prompt must cite `[n]` and admit when the archive
doesn't contain the answer. If keyword search finds nothing, the most
recent messages are offered as labeled fallback context.

**Search normalization.** `normalize_text` lowercases, strips Arabic
diacritics/tatweel, and unifies alef/ya/taa-marbuta variants, so `مطاعم`
matches `مطاعم` and vice versa. The trigram tokenizer handles substring
matching in both languages.

**Local-only posture.** No auth in-app; the default bind is `127.0.0.1`.
The docs and UI disclose exactly what leaves the machine (Ask-AI excerpts,
on request, to your chosen endpoint).
