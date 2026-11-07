# Privacy

Telegram Query is built to keep your data yours. This page documents
exactly what stays local and what can leave your machine.

## What stays on your machine

- **All messages** — stored in your SQLite database (`data/messages.db`)
- **Your Telegram session and credentials** — `tg_session.session` and `.env`
- **Searches, filters, AI chat history** — stored in your browser's
  localStorage; they never reach any server
- **Group lists, sync state, logs** — local files only

## What can leave your machine

Only two channels exist, and both are yours to control:

1. **Telegram** (required for syncing). The app talks to Telegram's API
   using *your* API ID/hash and session, exactly like a Telegram client
   you wrote yourself. Telegram sees which groups you fetch.
2. **Your AI provider** (optional, only when you click *Ask*). The
   question plus the retrieved message excerpts are sent to the endpoint
   you configured (`AI_BASE_URL`). The UI shows this disclosure next to
   the composer at all times. Do not configure an AI provider and nothing
   ever leaves your machine beyond Telegram sync traffic.

## What is NOT done

- No telemetry, analytics, or crash reporting.
- No third-party CDNs — fonts, icons, and the frontend bundle are served
  from your local app.
- No message content is written to the server log: sync logs contain
  group titles and counters only. (Search terms appear in standard uvicorn
  access lines, which also stay local.)
- API keys are never sent to the browser; the UI only learns whether AI is
  configured and the provider host for the disclosure line.

## Deletion

- Remove a group, keep data: **Untrack** stops archiving it and hides its
  messages from the app. The rows stay on disk and reappear if you track
  the group again (a full backfill runs, but it is mostly a no-op).
- Remove a group and its data: **🗑 delete** (next to untrack in Manage
  groups) permanently removes that group's messages from the database and
  resets its sync state. This cannot be undone; re-tracking re-downloads
  the history from Telegram.
- Delete everything: stop the app and delete the `data/` directory and
  `.env`. To revoke the app's Telegram access, also terminate the session
  from Telegram's "Active sessions" settings.

## Data minimization defaults

- Ask-AI context is capped (`AI_MAX_SOURCES`, default 80 messages,
  each truncated) — you control the ceiling.
- Only tracked groups are archived. Untracked groups are never read.
