# Privacy

Telegram Query is built to keep your data yours. This page documents
exactly what stays local and what can leave your machine.

## What stays on your machine

- **All messages** — stored in your SQLite database (`data/messages.db`
  for source runs; `%LOCALAPPDATA%\TelegramQuery\messages.db` for the
  Windows desktop app)
- **Your Telegram session and credentials** — `tg_session.session` and
  `.env` (both inside the data dir)
- **Searches, filters, AI chat history** — stored in the app window's
  localStorage; they never reach any server
- **Bookmarks and private notes** — stored in your database. Notes are app
  metadata: they are **never** included in AI retrieval context and are
  deleted together with their message
- **Saved searches, deals, decisions, research briefs, digests, FAQ
  records** — all generated and stored locally; exports write to files
  you download
- **Decision follow-up checks and the Evidence Explorer** (v0.8) —
  deterministic keyword matching and pure SQL joins over your local
  archive; neither ever calls an AI provider
- **The entire Discover view (v0.7)** — trending topics, cross-group
  stories, unanswered questions, group activity, and the entity
  gazetteer's mention matching are deterministic: computed from your
  local archive with **zero AI calls**. Entity discovery via AI is
  opt-in (off by default).
- **Watchlists and alerts** — pure keyword matching against your local
  archive; this feature never calls an AI provider at all
- **AI usage records** — request counts and token estimates per feature
  (and the model that served them), kept in your database for the
  Settings display
- **Group lists, sync state, auto-sync schedule, logs** — local files only

## What can leave your machine

Only two channels exist, and both are yours to control:

1. **Telegram** (required for syncing). The app talks to Telegram's API
   using *your* API ID/hash and session, exactly like a Telegram client
   you wrote yourself. Telegram sees which groups you fetch.
2. **Your AI provider** (optional — nothing is sent unless you trigger an
   AI feature). The following send **retrieved message excerpts** to the
   endpoint you configured (`AI_BASE_URL`), never your whole archive:
   - **Ask-AI** — your question plus retrieved excerpts (scope chips show
     exactly which groups/dates are searched)
   - **Deals extraction** — batches of keyword-matched candidate messages,
     either on demand (visible job) or incrementally after a sync when you
     enable auto-extraction; unchanged batches are served from a local
     cache and re-sent to no one
   - **Decision extraction** (v0.8) — the same shape as deals: batches of
     keyword-matched candidate messages, on demand (visible job) or
     incrementally after a sync when you enable auto-extraction;
     unchanged batches are served from a local cache and re-sent to no one
   - **Research briefs** — retrieved excerpts for the brief's scope, plus
     the question
   - **Digests** — the period's messages (capped), for on-demand or
     scheduled generation; unchanged periods are never re-sent
   - **FAQ answer drafting** — the clustered question variants plus nearby
     answer candidates; only for questions that recur
   - **Entity discovery** (opt-in, off by default) — batches of new
     messages above a per-chat watermark, only when you enable it in the
     Entities view; unchanged batches are served from a local cache
   - **Topic timelines** (Discover → "Timeline") — retrieved excerpts for
     one topic, capped and deduplicated; an unchanged topic is served
     from the local cache

   The UI discloses the provider next to each trigger (Ask-AI composer,
   Deals/Decisions toolbars, digest/deal buttons). Do not configure an AI
   provider and nothing ever leaves your machine beyond Telegram sync
   traffic.

## What is NOT done

- No telemetry, analytics, or crash reporting.
- No third-party CDNs — fonts, icons, and the frontend bundle are served
  from your local app.
- No message content is written to the server log: sync logs contain
  group titles and counters only. (Search terms appear in standard uvicorn
  access lines, which also stay local.)
- API keys are never sent to the browser; the UI only learns whether AI is
  configured and the provider host for the disclosure line.
- AI outputs are never silently trusted: extracted deals and decisions
  cite verifiable source messages, brief/digest/FAQ citations are
  validated on the backend against your real archive, and FAQ answers
  require your approval before they count as knowledge.

## Deletion

- Remove a group, keep data: **Untrack** stops archiving it and hides its
  messages from the app. The rows stay on disk and reappear if you track
  the group again (a full backfill runs, but it is mostly a no-op).
- Remove a group and its data: **🗑 delete** (next to untrack in Manage
  groups) permanently removes that group's messages from the database and
  resets its sync state. Bookmarks, deal/decision sources, brief/digest
  citations, and alerts pointing at those messages are removed with them
  (foreign keys cascade). This cannot be undone; re-tracking re-downloads
  the history from Telegram.
- Delete everything: use **Settings → Data → Erase all data** (packaged
  app — typed `ERASE` confirmation) or stop the app and delete the data
  directory (`data/` for source runs,
  `%LOCALAPPDATA%\TelegramQuery\` for the desktop app) and `.env`.
  Uninstalling the desktop app does **not** delete your data — the data
  folder survives uninstall by design, so erasing is explicit.
  To revoke the app's Telegram access, also terminate the session
  from Telegram's "Active sessions" settings.

## Data minimization defaults

- Ask-AI context is capped (`AI_MAX_SOURCES`, default 80 messages,
  each truncated) — you control the ceiling.
- Deal extraction batches are keyword-filtered candidates only, capped per
  batch; incremental runs read only messages above a per-chat watermark.
- Decision extraction follows the same rule: keyword-filtered candidates
  only, capped per batch, above a per-chat watermark for incremental runs.
- Digests cap the period's messages (500) and collapse duplicates before
  anything is sent.
- Research briefs retrieve within the scope you pick and expand context
  only with replies and near-in-time neighbors, within a fixed budget.
- Only tracked groups are archived. Untracked groups are never read.
