# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-11-11

First desktop release: Windows installers, a full UI/UX overhaul, and
a bilingual (EN/AR + true RTL) workspace. Schema unchanged from v9;
additive API only. Details: [release-notes.md](release-notes.md).

### Added
- **Windows packaging**: PyInstaller onedir build (`desktop.py` entry,
  windowed, no console), WiX MSI + Burn setup EXE from one shared
  definition, per-machine install with shortcuts and a single
  Add/Remove-Programs entry, fixed upgrade GUIDs, SHA-256 checksums
  (`scripts/build_windows.py`, CI job `packaging`).
- **Desktop runtime** (`desktop.py`): named-mutex single instance,
  loopback-only bind, busy-port fallback recorded in `runtime.json`,
  health-gated browser open, explicit quit with graceful shutdown,
  rotating file log, native crash dialogs.
- **User-data placement** (`config.py`, frozen-aware): packaged builds
  keep mutable data in `%LOCALAPPDATA%\TelegramQuery` — never inside
  Program Files; uninstall preserves it by design.
- **Copy-based archive migration** (`migration.py`): never overwrites,
  backs up, idempotent, interrupt-safe; preserves the Telegram session
  and settings.
- **Erase API + Settings action** (`api/data.py`): explicit, typed-
  confirmation full cleanup for the packaged app.
- **UI design system** (`web/src/design/`): token-based themes
  (layered surfaces, type scale, elevation, motion), self-hosted
  Inter Variable + Noto Sans Arabic, per-view stylesheets.
- **Lucide icon system** (`web/src/design/icons.tsx`): every emoji in
  the UI replaced; one stroke weight; directional icons auto-mirror
  in RTL.
- **Bilingual UI** (`web/src/i18n/`): English/Arabic switch, per-view
  string tables, `<html lang/dir>` set before first paint, logical
  CSS properties throughout, `dir="auto"` on user content.
- **Packaged-app test harness** (`scripts/test_packaged_app.py`):
  launch → port discovery → health payload → data isolation →
  single-instance → graceful-quit checks.
- Bundled `cryptg` for native-speed Telegram crypto in packaged builds.

### Changed
- Feed: memoized message cards + stable handlers — store updates no
  longer re-render the feed.
- Visual refresh of every workspace (Discover, Browse, Bookmarks,
  Deals, Decisions, Research, Watchlists, Alerts, Digests, FAQs,
  Entities, AI panel, Details panel, onboarding) with focus-visible
  rings and restyled empty/loading states.
- CI gains a Windows `packaging` job producing the installers as
  artifacts; `web/package.json` now tracks `config.__version__`.

## [Unreleased]

## [0.9.0] - 2026-11-10

Production readiness & performance engineering pass. Every change is
measured in `docs/engineering/` (audit → baseline → optimization →
validation). Schema migration v8 → v9 (additive; replaces one redundant
index with a prefix-compatible composite and refreshes planner stats).
No API contract changed; two endpoints and one env var were added.

### Added
- **Health/ready split**: `GET /api/health/ready` (readiness — checks
  the archive DB; optional dependencies are informational and can never
  fail it) alongside the dependency-free `GET /api/health` liveness.
- **`TGQ_AI_MAX_CONCURRENCY`** (default 4): bounds provider requests in
  flight; saturated asks wait up to the request timeout, then get an
  honest 503. Protects the request threadpool from provider-latency
  pile-ups.
- **`scripts/backup_db.py`**: online, consistent, compacted snapshots
  (`VACUUM INTO`) with retention; restore procedure documented in
  `docs/engineering/DATABASE_OPERATIONS.md`.
- **`scripts/benchmark.py`**: repeatable performance harness (real
  ingestion path, direct DB queries with plans, real-app HTTP latency
  P50/P95/P99 + throughput + RSS) at 5k/50k/500k-row scales. Caught a
  1,000× pagination regression during development — now a standard
  gate for SQL/schema changes.
- **Graceful shutdown**: running jobs are cancelled at their checkpoint
  (≤5 s wait), and module state is left clean for the next instance.
- **CLI sync guard**: `python sync.py` refuses to share the Telegram
  session with a running web app (`--force` to override).
- Static assets served with `Cache-Control: immutable` (hashed names),
  `no-cache` index, and `nosniff` / `X-Frame-Options` / `Referrer-Policy`
  response headers. Non-loopback `HOST` logs a loud warning at startup.
- Real token usage recorded for the Ask-AI pipeline (was `None` even
  when providers report usage).
- **docs/engineering/**: architecture audit, performance baseline,
  optimization report, feature development guide, security review,
  production deployment guide, database operations runbook.

### Changed
- **Schema v9** — keyset pagination is index-satisfiable by
  construction: new composite `(date, chat_id, msg_id)` index with
  row-value cursors, plus `(chat_id, sender_name)` and `(chat_id,
  reply_to)` indexes; planner statistics (ANALYZE) refresh after syncs
  on a doubling threshold. Measured at 500k rows: groups 150→22 ms,
  senders 283→148 ms (filtered 110→39), conversation 14→3 ms,
  deep pages 64% faster; ingestion of identical messages no longer
  churns the FTS index (zero FTS writes on day-rescans).
- **Search** ranks in a subquery with all filters applied before the
  LIMIT and joins only afterward (result sets identical; pinned by
  tests). Ask-AI retrieval runs one ranked window-function query per
  attempt instead of one full search per tracked chat.
- **WAL `synchronous=NORMAL`** + 8 MB page cache per connection.
- Provider client is cached process-wide (rebuilt when settings change)
  instead of per ask / per retry attempt.
- Browse pages no longer ship `text_norm` (no consumer anywhere) —
  ~21% smaller feed payloads.
- Frontend cancels superseded feed/search requests (AbortController)
  and debounces the senders fetch.
- All syncs-failed is now an honest job failure (the scheduler no
  longer records a bogus `last_success`); a `--days`-rescan that hits
  errors can't silently report success.
- Dependency floors gained majors-only upper bounds (the installed set
  — fastapi 0.141 / openai 3.x / telethon 1.45 — is what CI tests).

### Fixed
- Sync chat failures no longer update `last_synced`/report success when
  every tracked chat failed.
- E2E version assertion compared against a stale constant instead of
  `config.__version__`.

## [0.8.1] - 2026-11-09

Completes the v0.8.0 P0 track: open decisions are watched
deterministically, and every citation becomes queryable in reverse.
Both features are pure keyword/SQL work — no AI, no new provider
surfaces.

### Added
- **Follow-up tracking** (v0.8 P0 #2): every open decision is watched
  deterministically after each sync — newer messages that discuss it
  (matching ≥ 2 of its title keywords over normalized text) are stored
  as per-decision follow-ups with their matched terms, shown as a
  follow-up section on the decision card, and counted on a monitor
  strip. Incremental by construction: stored follow-ups advance a
  per-chat watermark, so re-runs only see genuinely new messages. No
  AI involved — pure keyword matching, the shared bilingual stopword
  pack, and the existing FTS index. A due-date monitor surfaces
  overdue and due-within-7-days decisions; a "Check follow-ups"
  button runs the check on demand.
- **Evidence Explorer** (v0.8 P0 #3): select any message and the
  Details panel shows everything that references it — deals, decisions
  (as source *or* follow-up), research briefs, digests, alerts, FAQs
  (as question or answer side), and entities — plus its thread
  context (parent + direct replies, honest about pre-v0.5 `reply_to`
  gaps). Each back-reference deep-links to the referencing record and
  expands it (Deals/Decisions focus the row). Read-only, pure SQL,
  no AI; unifies the whole citation story. Schema migration v7 → v8
  (additive, idempotent).

## [0.8.0] - 2026-11-09

Knowledge Intelligence: turning conversations into structured, reusable
knowledge that keeps verifiable references to its original messages.
The first release of the v0.8 line adds the decisions & commitments
tracker; follow-up tracking and the Evidence Explorer follow.

### Added
- **Decisions & commitments tracker** (first v0.8 Knowledge Intelligence
  feature): team decisions, agreements, and action items inside your
  groups become typed rows (decision text, kind, owner, due date,
  status) with per-row citations, cross-group dedupe, human
  confirm/dismiss/correct controls, exports (MD/JSON), an on-demand
  extraction job, and opt-in incremental extraction after each sync.
  Status is evidence-derived, never model-invented: `completed`/
  `cancelled` come only from the message's own words, a past due date
  reads `overdue`, and a record without evidence reads `unverified` —
  nothing is ever silently "committed" forever. Extraction only sends
  keyword-matched candidate messages (cached by fingerprint), never the
  whole archive. Schema migration v6 → v7 (additive, idempotent).

## [0.7.1] - 2026-11-09

### Fixed
- A tracked chat that Telegram can no longer resolve (deleted, migrated to
  a supergroup, account left/kicked) no longer aborts the whole sync job.
  The sync now logs that chat's title with an untrack hint
  (`python sync.py --untrack <id>`) and continues with the remaining
  chats; previously one dead group killed the entire run and every chat
  after it went unsynced until it was removed.
- Sidebar group list squished by tall nav (v0.7 Discover added 5 nav items).
  The Groups section and sync card now have `min-height` guards and the
  sidebar itself scrolls when content exceeds the viewport, so every
  group row and the sync card remain usable on standard laptop screens.

### Changed
- `docs/installation.md`: add restart-after-upgrade warning (stale
  processes mix old in-memory modules with new on-disk code) and
  troubleshooting rows for the two sync symptoms above.

## [0.7.0] - 2026-11-08

Community Discovery: understand what's happening across your communities
without reading everything. The whole discovery core is deterministic -
no AI provider required, no cost per message - and the app now opens on
a Discover view instead of the raw feed.

### Added
- **Trending topics & term analytics**: per-group daily term counts
  (normalized unigrams + bigrams over `text_norm`, bilingual stopword
  pack) are built incrementally above per-chat watermarks after every
  sync - never a full-archive scan. Burst scoring compares the recent
  window against the prior one; every topic links to a real sample
  message and runs as a feed search in one click. `sort=burst|volume`.
- **Discover home (new landing view)**: trending topics (with per-topic
  "Timeline ✦"), cross-group stories, the unanswered-questions radar,
  and 30-day group activity with sparklines - every card reaches the
  original messages in ≤2 clicks. Group scope chips reuse the sidebar
  selection; "Rebuild data" re-runs the full backfill as a visible job.
- **Cross-group stories**: near-duplicate posts that appeared in 2+
  groups inside the window (forwarded announcements/offers) are grouped
  with every occurrence kept as a source; all-stopword chatter (greeting
  spam) is never a story.
- **Unanswered-questions radar**: questions detected with the same
  bilingual interrogative rules as FAQ discovery, tracked when they have
  no substantive reply. Replies arriving in later synces auto-resolve
  their parent; a reply that is itself a question is a follow-up, not
  an answer. Human statuses (answered/ignored) are never overwritten by
  rescans. When an APPROVED FAQ answer matches, it's offered inline -
  nothing becomes trusted knowledge without the existing human gate.
- **Entity recognition & tracking**: a gazetteer of brands, products,
  orgs, projects, places, events (NEVER individual people - no member
  analytics exists in this product). Seeded from extracted deal vendors,
  extended manually or by an opt-in AI discovery pass (extraction model,
  incremental batches, fingerprint-cached, honest failure). Mention
  matching is deterministic against `text_norm`; every mention keeps
  its source message (FK cascade). Merge/rename/ignore are human
  controls; per-entity trend, group spread, and a 30-day series.
- **Conversation view**: "View in conversation" on any message opens the
  reply chain (where captured) plus the same-chat window - honest about
  pre-0.5 messages lacking `reply_to`, never inferring messages.
- **Topic timeline ("what changed about X")**: retrieval for one topic,
  synthesized into a dated, cited timeline (synthesis model). Backend
  citation validation strips unresolvable markers; results cached by
  source fingerprint - an unchanged topic is never re-paid.
- **AI model routing**: optional per-task-type models over the same
  OpenAI-compatible endpoint - `AI_MODEL_EXTRACT` (cheap/fast structured
  tasks: deals, entity discovery, keyword extraction), `AI_MODEL_SYNTH`
  (answers, briefs, digests, FAQ answers, timelines), `AI_MODEL_EMBED`
  (reserved for the v0.8 embeddings benchmark). All fall back to
  `AI_MODEL`; nothing is hardcoded to a provider. Ask-AI already routes
  keyword extraction vs answering accordingly.
- **Daily AI budget guard**: `TGQ_AI_DAILY_CAP` (0 = unlimited) caps
  total AI requests per UTC day with honest errors; deterministic
  features are never affected. Usage is now recorded per model and
  surfaced in `/api/ai/usage`.
- Schema v6: `term_daily`, `entities`, `entity_mentions`,
  `open_questions`, `ai_usage.model` (additive-only; existing archives
  get a one-time visible discovery backfill job on the next start).
- Sidebar gains a "Discover" group (Discover, Entities); mobile bottom
  nav leads with Discover. `scripts/seed_demo.py` now seeds cross-group
  announcements, Q&A threads, unanswered questions, recurring brand
  mentions, and Arabic content - and pre-builds discovery data.

### Changed
- The app's landing view is Discover (Browse remains one click away).
- FAQ question detection is now shared explicitly (`faq.is_question`)
  by the unanswered-questions radar - one definition, no duplicate
  heuristics.

### Deferred (documented in docs/decisions/)
- Multi-account support (v0.10 candidate): rejected for now - single
  session is a core invariant; a second installation via `TG_DATA_DIR`
  is the supported pattern.
- Semantic/embedding retrieval: benchmark-gated for v0.8, off by
  default - FTS5 measured sufficient at 500k messages.
- Media/OCR: gated on the opt-in media cache planned for v0.10.

## [0.6.0] - 2026-11-07

Monitor: from reactive search to proactive knowledge discovery. Watchlists
and alerts are fully deterministic (no AI, no cost); digests and FAQ
answers are AI-drafted but citation-validated and human-gated.

### Added
- **Topic watchlists**: keyword monitors (Arabic/English, normalization-
  aware) with exclusions and per-group scope, evaluated incrementally after
  every sync against a per-chat watermark - never the whole archive.
  Alerts are deduplicated per watchlist+message, and matching never calls
  the AI provider. The Alerts inbox has new/read/archived states, per-
  watchlist filtering, jump-to-message, and verified Telegram links.
  "Check now" re-evaluates on demand, optionally rewinding to cover the
  last N days for newly created watchlists.
- **Digests**: cited daily/weekly summaries of selected groups.
  Deterministic theme hints (top terms) ground the model; every factual
  item cites `[n]` messages validated on the backend, empty sections are
  dropped by prompt contract, and unchanged periods are never re-sent to
  the provider (fingerprint caching + stored-digest reuse). Daily/weekly
  schedules ride the auto-sync loop; on-demand "digest last day/week"
  runs as a visible job. History, citations, delete, auto language
  detection.
- **FAQ discovery**: recurring questions are clustered deterministically
  (bilingual interrogative detection + token-similarity, conservative
  threshold so unrelated questions never merge); recurring clusters get a
  drafted answer from reply/near-time evidence with backend-validated
  citations. **Nothing becomes trusted knowledge without human approval**;
  new evidence against an approved answer flags it for re-review instead
  of silently replacing it. Approve / reject / mark outdated / edit answers;
  question sources are inspectable with deep links.
- Sidebar gains grouped navigation: Knowledge (Deals, Research, FAQs) and
  Monitor (Watchlists, Alerts with unread badge, Digests).
- Schema v5: `watchlists`, `alerts`, `watch_watermarks`,
  `digest_schedules`, `digests`, `digest_citations`, `faq_clusters`
  (additive-only migrations, FK cascades on message deletion).
- Digest schedules are checked from the scheduler tick via the new
  `jobs.TICK_HOOKS` seam.

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
