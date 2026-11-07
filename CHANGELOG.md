# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.5.0] - 2026-11-07

Remember + Research: the archive becomes structured, evidence-linked
knowledge. A shared AI-task layer keeps every AI feature provider-agnostic,
cached, schema-validated, and honest about failures.

### Added
- **Deals extractor**: commercial offers pulled out of your groups as typed
  rows (vendor, discount, price, currency, promo code, eligibility, geo,
  validity dates) with per-row citations to the original messages. Bilingual
  Arabic/English extraction; forwarded copies of the same offer merge with
  all their sources; offers never merge on loose similarity. Status is
  evidence-derived (active / expired / upcoming / unverified / unknown) and
  kept distinguishable from the model's own judgment; offers without
  validity evidence are never silently "active". Extraction runs as a
  visible background job over a scope, or incrementally after each sync
  (opt-in toggle) using per-chat watermarks; batch results are cached by
  source fingerprint so unchanged messages are never re-sent; malformed
  model output gets exactly one repair attempt and is otherwise discarded.
  The Deals workspace adds search, status/category/group/date filters,
  sorting, confidence labels (qualitative - never fake probabilities),
  human confirm/dismiss, expiry correction, manual add (human-confirmed by
  design), and Markdown/JSON export.
- **Research briefs**: ask a question, pick groups + a date scope, get a
  structured, citation-linked brief (saved, re-runnable, versioned - old
  versions are preserved). Retrieval expands context with reply targets
  (captured going forward via the new `messages.reply_to`) and near-in-time
  neighbors; every `[n]` citation is validated on the backend and
  unresolvable markers are stripped and reported. **Staleness is
  deterministic**: a badge counts scope-matching messages archived after
  the last run - the provider is never called when you open a brief.
  Briefs support re-run, rename, personal notes, delete, version history,
  provenance (model + prompt version), and MD/JSON export with citations.
- **AI task layer** (`ai_tasks.py`): one provider runner for all structured
  AI workflows - capability-aware (no JSON-mode assumptions), fence-
  tolerant parsing, schema validation with a single repair attempt,
  provider retries with backoff+jitter, per-fingerprint result caching,
  request/token usage recording per task, and versioned prompts whose
  version is stored with every output. Features stay functional without a
  provider and fail with honest errors.
- Post-sync hook seam now powers optional incremental deals extraction.
- Exports for deals and briefs (MD + JSON, citations and Telegram links
  preserved).

### Changed
- Ask-AI scope handling and the research keyword extraction share the
  provider abstraction; response parsing tolerates fences everywhere.
- Schema v4: `deals`, `deal_sources`, `briefs`, `brief_versions`,
  `brief_citations`, `ai_task_cache`, `ai_usage`, plus `messages.reply_to`
  capture (additive-only migrations; bookmarks/deal sources/brief
  citations cascade on message deletion).

## [0.4.0] - 2026-11-07

Strengthen the core: automatic sync, AI scope control, deep links,
saved searches, bookmarks with private notes, exports, and extended
Arabic/Arabizi search normalization. Same local-first, single-SQLite,
no-Docker architecture.

### Added
- **Auto-sync scheduler**: DB-persisted schedule (default on, every 6h,
  configurable 15 min - 7 days in Settings) that survives restarts and
  catches up after downtime. Shows next/last sync in the sidebar; never
  overlaps a running sync; manual sync always available.
- **AI scope chips**: Ask AI now shows exactly which groups and date range
  it will search - removable chips (selected groups from the sidebar +
  All time / 7 days / 30 days). Explicit scope overrides the model's own
  group/date guesses and restricts retrieval for real, including the
  recent-messages fallback.
- **Open-in-Telegram deep links**: verified `t.me` links per message for
  public groups (`t.me/<username>/<id>`) and private supergroups/channels
  (`t.me/c/<id>/<id>`, member-only by Telegram's design), with "copy
  message link" on feed details, bookmarks, and AI-source rows. Chats
  without message links (basic groups) say so instead of fabricating URLs.
- **Saved searches**: name the current query + filters (groups, dates,
  sender, media, sort) and re-run them any time. Saved searches store the
  definition, never stale result rows; rename/duplicate/delete inline in
  the sidebar; exportable as JSON.
- **Bookmarks & private notes**: star any message, attach a Unicode-safe
  Arabic/English note (4k chars), edit any time. Starred-only feed filter,
  full-text note search, and a dedicated Bookmarks workspace with jump-to-
  message and Telegram links. Notes are app metadata: they never enter AI
  retrieval context and are deleted with their message (cascading FK).
- **Exports**: Markdown + JSON downloads for bookmarks (with notes,
  citations, and Telegram links), saved searches (JSON), and any AI answer
  with its re-verified sources - UTF-8 with full Arabic support, safe
  filenames, no secrets ever.
- **Extended search normalization** (`NORMALIZATION`, default): Arabic-Indic
  digit folding (٢٥ → 25), chat-elongation collapse (هااااي → هاي), Arabizi
  digit folding inside Latin words (3arabi → عarabi; multi-digit runs like
  prices and promo codes are never folded), and a small configurable Gulf
  dialect map (شلون → كيف, وين → اين, ...; `TGQ_DIALECT_MAP` overrides).
  Index- and query-side stay consistent: a one-time background reindex
  (visible in Jobs, cancellable, resumable) is queued automatically after
  upgrading an existing archive; `NORMALIZATION=standard` keeps exact
  v0.3 behavior. Original message text is never modified.
- **Search normalization rebuild** action in Settings ("Rebuild search
  index") for manual re-indexing after rule changes.
- Post-sync hook seam in the job system (foundation for incremental
  knowledge features).

### Changed
- Ask AI responses now echo the applied scope and the provider model.
- New tables `app_settings`, `saved_searches`, `bookmarks` (schema v3) via
  additive-only, idempotent migrations; foreign keys enforced so
  bookmarks can never orphan.

## [0.3.0] - 2026-11-07

First public, open-source release. Productization of the personal
prototype: configuration, onboarding, frontend, testing, and docs.

### Added
- **Untrack options**: untrack keeps a group's messages on disk (hidden,
  reversible on re-track), while a separate double-confirmed **delete**
  action permanently removes them and resets the sync state. Archive
  stats now count only tracked groups so numbers always match the UI.
- **In-app credential setup**: the wizard (and Settings) now collect
  Telegram API credentials and the AI provider directly — masked inputs,
  provider presets (OpenAI, Groq, OpenRouter, Ollama…), a live
  "test connection" check, and values written to your local `.env` with
  hot-reload. Secrets are write-only: never echoed back or logged.
- Centralized configuration (`config.py`, `.env.example` reference) — every
  path, credential, and provider setting is environment-driven; legacy
  `TELEGRAM_API_*` names and legacy file locations keep working.
- In-app Telegram login wizard (phone → code → optional 2FA) via
  `/api/auth/*`; non-interactive auth check for background jobs (fixes the
  silent stdin hang for fresh installs); `python sync.py --login` as the
  CLI alternative.
- `/api/app/state` first-run state endpoint powering a 5-step onboarding
  wizard and nine designed empty states.
- React + TypeScript + Vite frontend (`web/`) with a committed production
  build (`web/dist`) — light/dark themes, resizable panels, mobile
  bottom-nav, search history, active-filter chips, AI chat history with
  clickable citations that open the original message, job center with
  status chips / retry / cancel, and group discovery with live progress.
- Job system: ordered queue with dedupe and priority, stop-at-checkpoint,
  queue cancellation, retry, and completion detection.
- Backfills are checkpointed (`chats.backfill_floor`) — pause/resume
  without losing progress; versioned, additive-only DB migrations.
- Incremental FTS5 index maintenance (no more full rebuilds during sync).
- Test suite: 36 backend tests (mocked Telethon + mocked OpenAI) and 17
  frontend tests; GitHub Actions CI (ruff, pytest 3.10–3.13, vitest, build).
- Documentation: README, installation, configuration, architecture,
  privacy; CONTRIBUTING, SECURITY; synthetic demo seeder
  (`scripts/seed_demo.py`).

### Changed
- Ask-AI is fully generic (no domain assumptions), with balanced
  cross-group retrieval, an optional `TGQ_GROUPS_HINT`, recent-messages
  fallback, and provider disclosure in the UI.
- Ask-AI requests are validated (length caps) and errors return clean JSON.

### Fixed (release audit)
- Ask-AI provider failures (timeout, bad key, unknown model, rate limit)
  now return readable, actionable errors instead of a generic 500; the AI
  client uses an explicit 90s timeout.
- Local-app request hardening: a Host-allowlist middleware rejects
  requests addressed to other hosts (blocks cross-site form POSTs and DNS
  rebinding). Extra hosts opt-in via `TG_ALLOWED_HOSTS`.
- Setup endpoints validate credential values strictly, preventing `.env`
  line injection via newlines.
- The answer prompt now instructs the model to treat archived messages as
  data, not instructions (prompt-injection hardening), and out-of-range
  citations in the UI warn instead of silently doing nothing.
- Search query length is capped; archive stats count only tracked groups.
- Dev-toolchain CVEs cleared (`npm audit`: 0 vulnerabilities; vite 6,
  vitest 5); Python runtime deps audited clean in a fresh venv.
- Test-fixture data isolation: external-content FTS cleanup now rebuilds
  the index (DELETE FROM the FTS table is a no-op and leaked stale entries
  across tests).

### Removed
- Legacy single-file UI (`static/index.html`) — superseded by the React
  frontend; halved the surface area needing maintenance.
- `run_sync.cmd` personal helper — `python sync.py` is documented instead.
