# Configuration Reference

All configuration is environment variables; a `.env` file next to the app
is loaded automatically (copy `.env.example` to start). **The setup wizard
writes these values to `.env` for you** — manual editing is the power-user
alternative, not a requirement. Values changed in the wizard apply
immediately (settings hot-reload) and survive restarts.

Secret values are write-only: the app never sends them back to the browser
or writes them to logs.

## Resolution rules

- Session and database paths resolve in this order:
  1. explicit variable (`TG_SESSION_PATH` / `TG_DB_PATH`)
  2. legacy files next to the app root (`tg_session.session` / `messages.db`)
     — keeps pre-existing installations working
  3. default under the data dir: `data/`
- Legacy `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` names are accepted as
  aliases of `TG_API_ID` / `TG_API_HASH`.

## Telegram

| Variable | Default | Purpose |
|---|---|---|
| `TG_API_ID` | — | API ID from my.telegram.org (required) |
| `TG_API_HASH` | — | API hash from my.telegram.org (required) |
| `TG_SESSION_PATH` | `data/tg_session` | Telethon session file (auth state) |
| `TG_DATA_DIR` | `data` | Parent for defaults below |
| `SYNC_DAYS` | `3` | Days re-scanned by the sync button to catch edits |

## Storage

| Variable | Default | Purpose |
|---|---|---|
| `TG_DB_PATH` | `data/messages.db` | SQLite archive location |

## AI provider (optional — Ask-AI)

Any OpenAI-compatible chat-completions endpoint works: OpenAI, Azure,
Groq, Together, OpenRouter, Ollama (`http://localhost:11434/v1`), LM
Studio, vLLM, and compatible local servers.

| Variable | Default | Purpose |
|---|---|---|
| `AI_BASE_URL` | OpenAI | Base URL of the endpoint |
| `AI_API_KEY` | — | Key; Ask-AI stays disabled until set |
| `AI_MODEL` | `gpt-4o-mini` | Model name as the endpoint expects it |
| `AI_TEMPERATURE` | `0.2` | Generation temperature |
| `AI_MAX_SOURCES` | `80` | Max messages sent as context per question |
| `TGQ_GROUPS_HINT` | — | Free-text description of your communities, injected into the keyword extractor to sharpen retrieval (e.g. "local restaurant deal groups in Riyadh") |

## Server

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `127.0.0.1` | Bind address — **keep local**; see [SECURITY.md](../SECURITY.md) |
| `PORT` | `8000` | Listen port |
| `LOG_LEVEL` | `INFO` | Python logging level for the server log |
| `TG_ALLOWED_HOSTS` | — | Comma-separated extra Host headers the API accepts (the middleware only allows loopback + the configured host by default; only add hosts if you deliberately expose the app on your LAN) |
