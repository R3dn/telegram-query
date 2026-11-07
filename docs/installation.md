# Installation

## Requirements

- **Python 3.10 or newer** (3.13 tested)
- A Telegram account
- *Optional:* an API key for any OpenAI-compatible provider (enables Ask-AI)
- *Not required:* Node.js — the frontend build (`web/dist`) is committed.
  Node 20+ is only needed to modify the frontend.

## Steps

### 1. Get the code

```bash
git clone https://github.com/<you>/telegram-query.git
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

## Troubleshooting

| Symptom | Fix |
|---|---|
| Wizard says credentials missing | Edit `.env`, then press *Check again* — the file is read at startup, so restart `python app.py` if it still fails |
| Login code never arrives | Telegram sends it to the app on your phone first, SMS second — check Telegram itself |
| "A background job is using the Telegram session" | One Telegram operation at a time — stop the running job in the Jobs panel first |
| Sync seems slow | Large backfills download entire history; they're checkpointed, so you can stop and resume anytime |
| `database is locked` in logs | Only if you run two instances against the same DB — don't |
