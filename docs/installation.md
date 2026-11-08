# Installation

## Requirements

- **Python 3.10 or newer** (3.13 tested)
- A Telegram account
- *Optional:* an API key for any OpenAI-compatible provider (enables the
  AI features: Ask-AI, deal extraction, research briefs, digests, FAQ
  answer drafting, opt-in entity discovery, and topic timelines —
  everything else, including the whole Discover view, works without one)
- *Not required:* Node.js — the frontend build (`web/dist`) is committed.
  Node 20+ is only needed to modify the frontend.

## Steps

### 1. Get the code

```bash
git clone https://github.com/R3dn/telegram-query.git
cd telegram-query
```

### 2. Install dependencies

A virtual environment is recommended:

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Get Telegram API credentials

Third-party apps need their own API ID/hash (free, ~1 minute):

1. Open <https://my.telegram.org> → **API development tools**
2. Create an app — any title; other fields can stay default
3. Copy **api_id** and **api_hash**

You can paste them straight into the setup wizard (step 5) — no file editing
needed. If you prefer configuring by hand, create the file instead:

```bash
cp .env.example .env
```

…and fill in at minimum:

```ini
TG_API_ID=123456
TG_API_HASH=your_api_hash_here
```

### 4. Run

```bash
python app.py
```

Open <http://127.0.0.1:8000>. The wizard walks you through the rest:
credential check → Telegram login (phone + code + optional 2FA) → picking
groups → optional AI provider (with a live test button) → first sync.
Anything the wizard saves goes into your local `.env` and can be edited
there later.

### Try it without Telegram (synthetic data)

```bash
python scripts/seed_demo.py
```

The demo archive seeds cross-group announcements, Q&A threads, unanswered
questions, recurring brand mentions, and Arabic content, then pre-builds
the discovery data — the Discover view opens alive.

Then run the app against the demo database instead of your real one:

```bash
# macOS / Linux
TG_DB_PATH=data/demo.db TG_SESSION_PATH=data/demo python app.py

# Windows PowerShell
$env:TG_DB_PATH="data/demo.db"; $env:TG_SESSION_PATH="data/demo"; python app.py

# Windows CMD
set TG_DB_PATH=data/demo.db && set TG_SESSION_PATH=data/demo && python app.py
```

## CLI alternative

The wizard's login step can be done in a terminal instead:

```bash
python sync.py --login     # prompts for phone + code (+ 2FA if enabled)
```

All other operations (`--list`, `--track`, `--sync`) work from either the
web UI or the CLI.

## Upgrading

Pull the new version and reinstall dependencies if `requirements.txt`
changed. Database schema changes are applied automatically on startup and
are **additive-only** — your archive is never dropped or rewritten. The
only files that matter are your `.env` and your `data/` directory; backing
those up backs up everything.

Upgrading to v0.4 or later from a pre-v0.4 database queues a one-time
**Reindex** job on first start: search normalization improved (Arabizi,
Gulf dialect, elongation), and the index is rewritten in the background to
match — visible in the Jobs panel, cancellable, and resumed on the next
start if interrupted. You can also trigger it manually from
**Settings → Rebuild search index**.

Upgrading to v0.7 from a pre-v0.7 archive queues a one-time **Discover
backfill** job on first start: term statistics, unanswered questions, and
entity mentions are computed for your existing messages so the new
Discover view opens complete — visible in the Jobs panel, and discovery
is incremental from then on (deterministic; no AI involved).

## Troubleshooting

| Symptom | Fix |
|---|---|
| Wizard says credentials missing | Edit `.env`, then press *Check again* — the file is read at startup, so restart `python app.py` if it still fails |
| Login code never arrives | Telegram sends it to the app on your phone first, SMS second — check Telegram itself |
| "A background job is using the Telegram session" | One Telegram operation at a time — stop the running job in the Jobs panel first |
| Sync seems slow | Large backfills download entire history; they're checkpointed, so you can stop and resume anytime |
| Sync log: "[group] skipped - chat ID is invalid" | That tracked group no longer resolves — deleted, migrated to a supergroup, or your account left it. The sync skips it and continues; untrack it (`python sync.py --untrack <id>`, find the ID with `--list` or Manage groups) and track the new ID if it migrated |
| `database is locked` in logs | Only if you run two instances against the same DB — don't |
