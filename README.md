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
  <img src="docs/screenshots/discover-dark.png" alt="Discover trending topics (dark theme)" width="49.5%">
  <img src="docs/screenshots/discover-light.png" alt="Discover trending topics (light theme)" width="49.5%">
</p>

<p>
  <img src="docs/screenshots/feed-dark.png" alt="Browse your archive with day separators and media filters">
</p>

<p>
  <img src="docs/screenshots/search.png" alt="Full-text search with Arabic / English term highlighting">
</p>

<p>
  <img src="docs/screenshots/onboarding.png" alt="Setup wizard — API credentials and first sync">
</p>

## Quick start

Download **`TelegramQuery-Setup-x64.exe`** (or the plain
**`TelegramQuery-x64.msi`** for silent installs) from the
[latest release](https://github.com/R3dn/telegram-query/releases/latest)
and run it.

- No Python, Node, or other dependencies — it opens in its own app window
- Data lives in `%LOCALAPPDATA%\TelegramQuery`, survives upgrades and uninstalls
- The server binds to `127.0.0.1` only — nothing is exposed to the network
- The app is single-instance: a second click focuses the running window
- Minimize hides the window to the system tray (left-click tray icon to restore)
- The setup wizard walks you through Telegram login, group selection, and your
  first sync. Everything it saves lands only on your disk.

## Asking questions

Type a question in the Ask-AI panel — Arabic questions get Arabic answers:

- *"What were the main topics this week?"*
- *"ما أهم العروض المنشورة مؤخراً؟"*
- *"What problems do people report, and what fixed them?"*

Answers list the retrieved messages they are based on; every `[n]` citation
opens the original message.

> **Privacy note:** asking a question sends only the excerpts it retrieves
> to the AI endpoint you configured. Everything else stays local.

## Configuration

All settings are environment variables (loaded from `.env` in your data
folder, `%LOCALAPPDATA%\TelegramQuery\`). Copy `.env.example` to `.env` and
fill in your values.

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

The auto-sync schedule (on/off + interval) and all in-app settings are
configured in the UI and stored in your local database.

## Source run (development)

Requirements: **Python 3.10+**. Node is *not* required — the compiled
frontend is included under `web/dist/`.

```bash
git clone https://github.com/<you>/telegram-query.git
cd telegram-query
pip install -r requirements.txt
python app.py               # -> http://127.0.0.1:8000
```

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

## License

[MIT](LICENSE)
