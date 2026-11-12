# Telegram Query

**A local-first, searchable, AI-queryable archive for your Telegram groups.**

Connect your Telegram account, track the groups you care about, and turn
them into a private, searchable knowledge base you own. The app opens on a
**Discover** view — trending topics, cross-group stories, unanswered
questions, and group activity — all computed deterministically from your
archive, no AI required. Browse full history with day separators and
filters, run full-text searches across Arabic and English, and ask questions
answered *only* from your actual messages — with clickable citations back to
the originals.

Everything runs on your machine: the messages, the database, and your
Telegram session never leave it.

## Quick start

The desktop app is the release — Telegram Query ships only as the
Windows installer.

### Windows (installer)

Download **`TelegramQuery-Setup-x64.exe`** (or the plain
**`TelegramQuery-x64.msi`** for silent installs) from the release page
and run it. No Python, Node, or other dependencies — it opens in its
own app window (Microsoft Edge WebView2 Runtime, preinstalled on
Windows 10/11), data lives in `%LOCALAPPDATA%\TelegramQuery`, survives
upgrades and uninstalls, and the app binds to loopback only.

### From source (development)

Requirements: **Python 3.10+**. Node is *not* required — the frontend
build is included.

```bash
git clone https://github.com/<you>/telegram-query.git
cd telegram-query
pip install -r requirements.txt

# 1. get your API credentials (one minute): https://my.telegram.org
#    -> API development tools -> create an app
#    (you'll paste them into the setup wizard - or pre-fill .env yourself)

# 2. run
python app.py               # -> http://127.0.0.1:8000
```

Open http://127.0.0.1:8000 — the wizard collects your API credentials,
walks you through Telegram login, lets you pick groups, optionally
configures an AI provider (with a live "test connection" button), and
starts your first sync. Everything it saves lands in your local `.env`.

## Asking questions

Type a question in the Ask-AI panel — Arabic questions get Arabic answers:

- *"What were the main topics this week?"*
- *"ما أهم العروض المنشورة مؤخراً؟"*
- *"What problems do people report, and what fixed them?"*

Answers list the retrieved messages they are based on; every `[n]` citation
opens the original message.

> **Privacy note:** asking a question sends only the excerpts it retrieves
> to the AI endpoint you configured. Everything else stays local.

## Command line

`sync.py` exposes everything the UI does, for scripting:

```bash
python sync.py --login        # interactive Telegram login, then exit
python sync.py                # incremental sync of tracked groups
python sync.py --list         # list your groups
python sync.py --track <id>   # track a group + full backfill
python sync.py --untrack <id>
python sync.py --days 3       # re-scan last 3 days (catches edits)
python sync.py --full         # re-fetch entire history
```

## Configuration

All settings are environment variables (a `.env` file is loaded
automatically). Copy `.env.example` to `.env` and fill in your values.

| Variable | Default | Purpose |
|---|---|---|
| `TG_API_ID` / `TG_API_HASH` | — | Telegram API credentials |
| `TG_SESSION_PATH` | `data/tg_session` | Session file location |
| `TG_DB_PATH` | `data/messages.db` | Archive database location |
| `SYNC_DAYS` | `3` | Edit re-scan window |
| `NORMALIZATION` | `extended` | Search normalization level (`standard` = v0.3 rules) |
| `TGQ_DIALECT_MAP` | built-in Gulf map | JSON override for dialect word mapping |
| `AI_BASE_URL` | OpenAI | Any OpenAI-compatible endpoint |
| `AI_API_KEY` | — | Enables Ask-AI when set |
| `AI_MODEL` | `gpt-4o-mini` | Model name |
| `AI_MODEL_EXTRACT` | falls back to `AI_MODEL` | Cheap/fast model for structured extraction |
| `AI_MODEL_SYNTH` | falls back to `AI_MODEL` | Model for answers, briefs, digests, timelines |
| `AI_MODEL_EMBED` | falls back to `AI_MODEL` | Reserved for hybrid retrieval |
| `TGQ_AI_DAILY_CAP` | `0` (off) | Max AI requests per UTC day |
| `TGQ_AI_MAX_CONCURRENCY` | `4` | Max provider requests in flight |
| `TGQ_GROUPS_HINT` | — | Optional community description for keyword extraction |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Local bind address — keep it local |

The auto-sync schedule (on/off + interval) is configured in the app's
Settings screen and stored in your local database.

## Architecture

FastAPI backend + React/TypeScript frontend (built output committed under
`web/dist`, served by the backend — no Node needed at runtime). SQLite
with WAL, an FTS5 trigram external-content index maintained incrementally,
and a single-slot job runner so the Telegram session is never used
concurrently.

## Operations

- **Backup** (online, consistent snapshot): `python scripts/backup_db.py`
- **Benchmarks** (repeatable perf harness): `python scripts/benchmark.py seed|db|api --messages 500000`
- **Health**: `GET /api/health` (liveness) · `GET /api/health/ready` (readiness)

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check . && pytest
cd web && npm install && npm run typecheck && npm test && npm run build
```

**End-to-end** (real app + deterministic mock AI provider + synthetic
archive - no real Telegram/LLM/keys):

```bash
python scripts/seed_demo.py --path data/e2e.db --messages 400
python scripts/mock_ai_server.py --port 8124 &
TG_DB_PATH=$PWD/data/e2e.db TG_SESSION_PATH=$PWD/data/e2e-session \
  TG_API_ID=123456 TG_API_HASH=e2e AI_BASE_URL=http://127.0.0.1:8124/v1 \
  AI_API_KEY=e2e AI_MODEL=e2e-mock PORT=8123 python app.py &
python scripts/e2e_test.py --base http://127.0.0.1:8123 --db data/e2e.db
```

**Interactive desktop smoke test** (the full window lifecycle through
the real `desktop.py` runtime):

```bash
pip install playwright && python -m playwright install chromium
python scripts/e2e_smoke_desktop.py
```

The run is fully isolated — its own data dir and its own `.env`
(via `TGQ_ENV_FILE`), so it can never touch your real archive or
credentials.

CI runs the same suite on every push.

## Known limitations

- Media is archived as a marker (`[image]`), not downloaded. An opt-in
  media cache is planned for a later release; OCR is gated on it.
- One Telegram account per installation (single session file). A second
  installation via `TG_DATA_DIR` is the supported pattern.
- No multi-user auth: the UI assumes the person at localhost is you.
- Search indexes message *text*; OCR of image content is out of scope.
- Messages deleted on Telegram remain in your archive (the archive is a
  historical record; untrack & delete removes them locally).
- Jobs that are queued but not yet started don't survive an app restart;
  running jobs checkpoint and resume on the next sync.

## License

[MIT](LICENSE)
