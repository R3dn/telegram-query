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

<p>
  <img src="docs/screenshots/discover-dark.png" alt="Discover trending topics across your communities (dark theme)" width="49.5%">
  <img src="docs/screenshots/discover-light.png" alt="Discover trending topics across your communities (light theme)" width="49.5%">
</p>

## Highlights

- **Local-first & private** — SQLite archive on your disk; no cloud, no
  telemetry. The server binds to `127.0.0.1` by default.
- **Community discovery** — the app opens on a **Discover** view:
  trending topics (deterministic burst scoring over a bilingual term
  index), the same post forwarded across your groups, unanswered
  questions, entity tracking (brands/products/places — never people),
  and group activity — every card jumps to the original messages.
  Works with **zero AI configuration**; an optional per-topic "timeline"
  adds cited AI synthesis.
- **Full-history sync + auto-sync** — checkpointed backfills that
  pause/resume without losing progress, incremental updates, edit
  detection, flood-limit handling, a job queue with stop/cancel controls,
  and a restart-proof automatic sync schedule (on by default, every 6h,
  configurable).
- **A real desktop app** — the Windows build opens in its own native
  window (Edge WebView2): single instance, a second launch focuses the
  running window, closing it quits gracefully, and minimizing hides it
  to the **system tray** (left-click the tray icon to restore, right-
  click for Open/Exit). A missing WebView2 runtime shows a clear error
  dialog with the download link instead of a broken window — there is
  no browser mode. The window fits your screen (small laptops and
  125–150 % scaling included), startup failures always show an honest
  error dialog with a log/dump location, and the in-app "erase all
  data" restarts you cleanly in the same session.
- **Fast bilingual search** — FTS5 trigram index with Arabic/English
  normalization: diacritics, alef/ya variants, taa marbuta, plus extended
  rules — Arabic-Indic digits (٢٥→25), chat elongation (هااااي→هاي),
  Arabizi folding inside Latin words, and a Gulf dialect map (شلون↔كيف) —
  with mixed-language queries, term highlighting, date/sender/media/star
  filters, and search history.
- **Grounded Ask-AI with visible scope** — questions in Arabic or English
  answered from retrieved messages only, with `[n]` citations that jump to
  the original message, removable scope chips showing exactly which groups
  and dates are searched, and one-click Markdown export. Works with any
  OpenAI-compatible endpoint (OpenAI, Groq, OpenRouter, Ollama, LM Studio,
  vLLM…). Optional — disable it and nothing ever leaves your machine.
- **Keep what matters** — star messages, attach private notes (never sent
  to AI), save searches under a name and re-run them any time, and open any
  message in its original Telegram chat with verified deep links.
- **Deals extractor** — offers inside your groups become typed rows (vendor,
  code, discount, expiry) with per-row citations, cross-group dedupe,
  evidence-derived status, human confirm/correct controls, and optional
  incremental extraction after each sync.
- **Decisions & commitments tracker** — team decisions, agreements, and
  action items become typed records (kind, owner, due date, status) with
  per-row citations, evidence-derived status (`overdue` for past due
  dates; nothing is silently "committed" without evidence), confirm/
  dismiss/correct controls, and optional incremental extraction after
  each sync. Open decisions are then watched deterministically: newer
  messages discussing them become follow-up citations, and a due-date
  monitor surfaces overdue and due-soon records — no AI required.
- **Evidence Explorer** — the reverse side of every citation: select any
  message and see everything that references it (deals, decisions,
  briefs, digests, alerts, FAQs, entities, thread context), each
  jumping back to the record that cites it.
- **Research briefs** — ask a question over selected groups and dates, get
  a saved, citation-validated, re-runnable brief with version history and
  deterministic staleness tracking.
- **Watchlists & alerts** — deterministic keyword monitors evaluated after
  every sync (no AI, no cost), with a new/read/archived alert inbox that
  jumps straight to the original message.
- **Digests & FAQs** — cited daily/weekly summaries on a schedule or on
  demand, and recurring questions clustered with drafted answers that
  nothing trusts until you approve them.
- **Works with zero groups on day one** — a built-in wizard walks you
  through API credentials, Telegram login (phone + code + 2FA), group
  selection, and your first sync.
- **Polished bilingual UI** — React frontend with light/dark themes,
  resizable panels, mobile navigation, first-class RTL and mixed-direction
  text rendering, and Markdown/JSON exports that are useful outside the
  app.

![Onboarding wizard](docs/screenshots/onboarding.png)

## Quick start

The desktop app is the release — Telegram Query ships only as the
Windows installer (decision 0010 in
[docs/decisions/README.md](docs/decisions/README.md)). "From source"
below is the development and contributor path.

### Windows (installer)

Download **`TelegramQuery-Setup-x64.exe`** (or the plain
**`TelegramQuery-x64.msi`** for silent installs) from the release page
and run it. No Python, Node, or other dependencies — it opens in its
own app window (Microsoft Edge WebView2 Runtime, preinstalled on
Windows 10/11), data lives in `%LOCALAPPDATA%\TelegramQuery`, survives
upgrades and uninstalls, and the app binds to loopback only. See
[docs/installation.md](docs/installation.md) for details.

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
See [docs/installation.md](docs/installation.md) for details, or try the
app with synthetic data instead: `python scripts/seed_demo.py`.

![Browse your archive](docs/screenshots/feed-dark.png)

![Search with highlights](docs/screenshots/search.png)

## Asking questions

Type a question in the Ask-AI panel — Arabic questions get Arabic answers:

- *"What were the main topics this week?"*
- *"ما أهم العروض المنشورة مؤخراً؟"*
- *"What problems do people report, and what fixed them?"*

Answers list the retrieved messages they are based on; every `[n]` citation
opens the original message.

> **Privacy note:** asking a question sends only the excerpts it retrieves
> to the AI endpoint you configured. Everything else stays local. See
> [docs/privacy.md](docs/privacy.md).

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
automatically). Full reference: [docs/configuration.md](docs/configuration.md).

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
| `AI_MODEL_EXTRACT` | falls back to `AI_MODEL` | Cheap/fast model for structured extraction (deals, entities, keywords) |
| `AI_MODEL_SYNTH` | falls back to `AI_MODEL` | Model for answers, briefs, digests, timelines |
| `AI_MODEL_EMBED` | falls back to `AI_MODEL` | Reserved for the (benchmark-gated) hybrid retrieval |
| `TGQ_AI_DAILY_CAP` | `0` (off) | Max AI requests per UTC day — honest errors when reached, deterministic features unaffected |
| `TGQ_AI_MAX_CONCURRENCY` | `4` | Max provider requests in flight; extra asks wait, then fail honestly |
| `TGQ_GROUPS_HINT` | — | Optional community description to sharpen keyword extraction |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Local bind address — keep it local |

The auto-sync schedule (on/off + interval) is configured in the app's
Settings screen and stored in your local database.

## Architecture

FastAPI backend + React/TypeScript frontend (built output committed under
`web/dist`, served by the backend — no Node needed at runtime). SQLite
with WAL, an FTS5 trigram external-content index maintained incrementally,
and a single-slot job runner so the Telegram session is never used
concurrently.

Details: [docs/architecture.md](docs/architecture.md). Engineering docs
(audit, performance baseline, optimization report, security review,
deployment/DB runbooks, feature guide):
[docs/engineering/](docs/engineering/).

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
the real `desktop.py` runtime: setup wizard with typed credentials,
click-navigation across every view, theme/language persistence across
a window restart, second-launch focus, graceful quit, and a
zero-console-errors gate):

```bash
pip install playwright && python -m playwright install chromium
python scripts/e2e_smoke_desktop.py
```

The run is fully isolated — its own data dir and its own `.env`
(via `TGQ_ENV_FILE`), so it can never touch your real archive or
credentials.

CI runs the same suite on every push.

Automated suites cover the DB/migrations, bilingual + Gulf/Arabizi search
normalization, sync checkpoints and resume, the job queue, the auto-sync
scheduler, the AI pipeline and scope (with a mocked provider - no real
credentials needed), setup/auth flows, saved searches, bookmarks and
notes, deep links, exports, the citation mapping in the frontend,
discovery (terms/stories/questions/entities/conversation), decisions
extraction (merge, evidence-derived status, human gates), deterministic
follow-up tracking, the Evidence Explorer (all citation tables), model
routing, and the daily budget cap. Contributions welcome - see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Known limitations

- Media is archived as a marker (`[image]`), not downloaded. An opt-in
  media cache is planned for a later release; OCR is gated on it.
- One Telegram account per installation (single session file). A second
  installation via `TG_DATA_DIR` is the supported pattern (see
  `docs/decisions/`).
- No multi-user auth: the UI assumes the person at localhost is you.
- Search indexes message *text*; OCR of image content is out of scope.
- Messages deleted on Telegram remain in your archive (the archive is a
  historical record; untrack & delete removes them locally).
- Jobs that are queued but not yet started don't survive an app restart;
  running jobs checkpoint and resume on the next sync (persistent queue
  is planned for v0.10).
- Discovery term stats and the question radar update after each sync;
  `reply_to` threading data is captured going forward (v0.5+), so older
  messages rely on the time-window fallback in conversation view.

## License

[MIT](LICENSE) — contributions under the same license.
