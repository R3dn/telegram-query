# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.3] - 2026-11-12

Windows desktop stabilization release from the v1.0.2 → v1.0.3
stabilization audit (`docs/engineering/windows-stabilization-audit.md`):
the erase flow, small-screen/high-DPI window placement, and honest
startup-failure reporting. No schema migration; existing archives
upgrade in place.

### Fixed
- **"Erase all data" left the running app broken (data lifecycle).**
  The erase action deletes the database file, and the UI reloads into
  the same process ~1.5 s later — but `db.get_db()` runs its
  one-time-per-path schema guard, so the next connection re-created an
  *empty* file with **no tables**: readiness returned 503 and every
  archive endpoint returned 500 until the app was restarted. The erase
  flow now drops the guard, so the very next request rebuilds a fresh,
  schema-complete empty archive (verified end-to-end through the API:
  readiness 200, search functional, state reports an empty archive).
- **"Erase all data" left the app claiming it was still configured.**
  The wizard persists credentials via `config.update_env`, which also
  sets them in the process environment; erasing the `.env` file alone
  left `telegram_configured`/`ai_configured` true for the rest of the
  session. The erase action now clears the app-managed credential
  variables and rebuilds settings, so the process honestly reports
  itself as unconfigured (and the wizard reopens at the credentials
  step) without a restart.
- **The window opened larger than the screen on small displays.**
  pywebview's WinForms backend multiplies the requested logical size by
  the monitor DPI and never clamps, so the 1400×900 default overflowed
  the screen on 1366×768 laptops (both axes) and at 125–150 % scaling
  on 1920×1080 displays (the window was physically larger than the
  monitor). The initial window is now clamped to the primary work area
  (taskbar excluded); any screen that fits the design size keeps it
  unchanged.
- **A backend that died during startup wasted the whole startup
  timeout.** The readiness poll never checked the server thread, so a
  uvicorn bind failure or startup crash made the user wait the full
  60 s timeout before the error dialog. The poll now notices a dead
  server thread within one interval and reports the honest reason
  ("the backend exited during startup", with the real cause in the
  log).
- **Early startup failures killed the windowed exe silently.** Before
  logging exists (data dir unwritable, disk full, `runtime.json` not
  writable), any exception escaped `main()` with no console, no log
  file, and no dialog — the app just didn't appear. Early and
  unexpected startup failures now show the native error dialog naming
  the data dir and write a crash dump to `%TEMP%` so the operator
  always has evidence.
- **The login toast showed an empty account name.** The wizard's
  success toast read the account label from the render-time state
  snapshot (always the pre-login value) instead of the login response
  that carries it.
- **The app would not open at all from the Start-Menu shortcut when the
  repository path contains a space** (e.g. `E:\AI Projects\...`). The
  shortcut's script path was written unquoted, so the interpreter
  received `E:\AI` as the script name and exited instantly — no window,
  no log, no error (a flashing error console under `python.exe`, fully
  silent under `pythonw`). The path is now quoted and pinned by an
  end-to-end test that launches the interpreter through a raw command
  line exactly like the shortcut does.
- **Clicking the app could appear to do nothing.** A second launch
  that found a live instance with no window (a headless/test instance,
  or one still starting or hung) exited **silently** — no window, no
  dialog, nothing, indistinguishable from a broken app. The handoff now
  always leaves the user with something: the focused window, or an
  honest dialog naming the situation and how to recover.
- **The dev Start-Menu shortcut flashed a terminal on every launch.**
  The shortcut created by source runs targeted `python.exe` — a console
  program — so every launch opened a black terminal that closed the
  moment the app exited or handed off, reading exactly like a crash.
  It now targets `pythonw.exe` (windowed, no console) when available.

### Tests
- 16 new backend regression tests (the erase/recreate lifecycle and the
  erase-while-job-running guard, window fitting at 100–200 % scaling,
  fail-fast startup reporting, the two startup-dialog paths, the
  never-silent second-launch handoff ×3, and the windowed-interpreter
  shortcut target ×3) and a new frontend suite
  (`web/tests/onboarding.test.tsx`, verified to fail on the unfixed
  code); full backend, frontend, desktop-E2E, and packaged-app suites
  re-run green.

## [1.0.2] - 2026-11-12

Stability and correctness release from the v1.0.1 full engineering
audit (`docs/engineering/bug-audit.md`): a critical sync-engine fix,
honest filter semantics, and coverage repairs for the knowledge
features. No schema migration; existing archives upgrade in place.

### Fixed
- **Critical: sync fetch errors no longer corrupt the archive
  watermark.** Telegram delivers messages newest-first; a fetch that
  died mid-way (network drop, RPC error) used to advance the chat's
  `last_msg_id` past messages Telegram never gave us, permanently and
  silently skipping the unfetched middle of the range — and a fresh
  backfill that failed before its first checkpoint was recorded as
  complete (`backfill_floor = 0`, "0 pending backfills") while most of
  the history was missing. Backfills now checkpoint partial progress
  exactly like the Stop button does, and failed scan/incremental
  fetches keep the pre-run watermark so the next sync re-walks and
  repairs the gap (duplicates are skipped by the idempotent upsert).
- **AI repair path**: `run_json_task` crashed with `UnboundLocalError`
  instead of running its one repair attempt when the first provider
  reply was not even parseable JSON and a `repair_system` prompt was
  supplied.
- **Media filter in search**: the FilterBar shows the images/text
  control in search mode, but `/api/search` silently ignored it. It is
  now honored end-to-end (`db.search`, API, client, store), and an
  invalid `media` value is an honest 400 rather than a silent filter
  drop (`/api/messages` validates identically).
- **Negative `limit` values** on the list endpoints no longer bypass
  result caps (SQLite treats `LIMIT -1` as unlimited — one request
  could serialize the whole archive); all endpoints clamp to
  `max(1, min(limit, N))` and `db.browse` guards its `limit + 1`
  arithmetic.
- **FAQ discovery coverage**: the 90-day scan window was read
  oldest-first, so busy archives (>1000 messages per window) silently
  never scanned recent questions. The window is now read newest-first
  (occurrences re-sorted so `first_seen` semantics are unchanged).
- **Deals incremental extraction**: the per-chat watermark advanced
  *before* the provider calls, so a provider failure mid-run
  permanently skipped those messages. It now advances only on success
  (and on empty windows), making failed runs self-heal on the next
  sync — unchanged batches are fingerprint-cache hits, so retries cost
  nothing. (`decisions` already had these semantics; `deals` was the
  divergent copy.)
- **Right panel responsiveness**: the 1100px layout breakpoint never
  re-evaluated after resizing the desktop window; it now reacts to
  window resizes.
- **AI chat history**: stable turn keys (`turn.at`) instead of index
  keys on the 50-turn front-trimming list (per-turn state could jump
  between turns after a trim).
- **Research brief notes (data integrity)**: switching briefs kept the
  previous brief's notes in the editor; saving then wrote one brief's
  notes onto another. The notes editor now resets with the selection.
- **Conversation panel**: selecting a different message kept showing
  the previous message's fetched thread; the block now resets with the
  selection.
- **Watchlists**: editing a paused watchlist no longer silently
  re-enables it (the save body hard-coded `enabled: true`).
- **Discover**: filter changes made during the first load are no
  longer swallowed (the 30-day tab could show 7-day data until some
  unrelated trigger), overlapping loads no longer let a slow older
  response win, and closing the topic-timeline panel while it is
  analyzing no longer gets resurrected by the late response.
- **Research briefs**: submitting no longer allows duplicate briefs
  (the busy flag never engaged because the job poller was never
  kicked); the citation row's "Open Telegram" control now actually
  opens Telegram.
- **FAQs**: "Save answer" no longer closes the editor and discards
  the typed answer when the save fails.
- **Evidence Explorer**: every "View" jump now focuses the referenced
  record (briefs opened the newest brief; digests/alerts/FAQs/entities
  landed unfocused; deals/decisions burned the focus when the target
  row was filtered out).
- **View-level races**: sequence guards and debounces across
  Deals/Decisions/Alerts/Entities/Digests loads (a slow older response
  could overwrite a newer one); the Manage-Groups dialog-listing poll
  loop stops when the modal closes; the weekly/daily schedule choice
  is no longer discarded by the schedule modal.

### Tests
- 10 new backend regression tests (sync checkpoints/watermarks, the AI
  repair path, search media + limit clamps, FAQ window coverage, the
  deals watermark) and a new frontend suite
  (`web/tests/v102.test.tsx`) pinning the brief-notes fix (verified to
  fail on the unfixed code); full backend, frontend, API-E2E, and
  desktop-E2E suites re-run green
  (`docs/engineering/release-validation.md`).

## [1.0.1] - 2026-11-12

Desktop-only point release: the native window + tray desktop runtime,
the wizard and right-panel fixes found in live UI testing, and the
recorded policy that the Windows desktop app is the only distribution
target (decision 0010 in docs/decisions/README.md).



### Added
- **Native app window** (`desktop.py`): the packaged app now opens in
  its own desktop window (pywebview + Microsoft Edge WebView2). Closing
  the window quits gracefully, the in-app Exit action closes the
  window, a second launch focuses the running window (by title, via
  `Win32`), and the UI's localStorage (theme, language, panel state)
  persists in `<data>/webview` instead of being wiped each launch.
  `--no-browser`/`TGQ_NO_BROWSER` still work and gained the clearer
  alias `--no-window`/`TGQ_NO_WINDOW`.
- **System tray icon** (`pystray`): the app minimizes to the notification
  area instead of the taskbar. Left-click the tray icon (or choose
  "Open") to restore the window; right-click for the menu. The tray
  uses the same Paper-Plane+lens mark as the executable. A missing icon
  degrades to a solid brand-colour placeholder.
- **WebView2 runtime gate**: before creating the window, the runtime
  checks the EdgeUpdate `pv` value (mirroring pywebview's threshold).
  A missing runtime would otherwise silently drop pywebview to the
  legacy MSHTML (IE) renderer, which cannot run the React UI. Since the
  browser fallback was removed, a missing runtime now shows an error
  dialog and exits. `runtime.json` records the UI mode so second launches
  know whether to look for a window.
- **`TGQ_ENV_FILE` override** (`config.py`): points the app at a
  different writable `.env`. Test harnesses use it to run the app
  against a throwaway file so a test can never read or write a real
  `.env`.
- **Window/taskbar icon on source runs**: `python desktop.py` now shows
  the app's mark in the taskbar and title bar (previously Python's
  generic icon). The full fix goes beyond `WM_SETICON` — Windows groups
  taskbar icons by the process *and* its AppUserModelID, not by the
  per-window icon. `desktop.py` sets the class icon via
  `SetClassLongPtrW`, assigns the explicit AUMID
  `Redn.TelegramQuery.Desktop`, and creates a Start Menu shortcut
  (`Telegram Query.lnk`) carrying the same AUMID and `app.ico`. The
  shortcut is created silently; `pywin32` is used if available, skipped
  otherwise. The packaged exe already has its icon from PyInstaller.
- **Interactive desktop smoke test** (`scripts/e2e_smoke_desktop.py`):
  boots the real `desktop.py` runtime fully isolated (own data dir +
  `.env` via `TGQ_ENV_FILE`) and drives the production UI end to end —
  setup wizard (typed + submitted credentials, step advance, re-open
  via the sidebar footer link), click-navigation across every view
  plus Ask AI, Jobs, and Settings modals, theme/language toggles,
  persistence across a full window restart, second-launch focus, and
  graceful quit — with a hard zero-console-errors gate. Dev-only
  dependency: Playwright.
- **`pywin32` is now a declared runtime dependency on Windows**
  (`sys_platform == "win32"` marker): `desktop.py`'s taskbar-icon /
  AUMID Start-Menu-shortcut path silently degrades without it, and a
  desktop-only release should never carry that gap. The marker keeps
  the Linux CI install intact; the runtime still skips gracefully if
  the package is absent.

### Changed
- **Setup wizard** (`web/`): on an already-configured install the wizard
  opens on a completion card; it now offers a "Change API credentials…"
  shortcut that jumps straight into the credentials edit form (the same
  form the Settings modal uses) instead of a dead end.
- **Packaging** (`TelegramQuery.spec`): bundles the pywebview/pythonnet
  window stack (hidden imports for `webview` + `edgechromium` +
  `winforms` + `clr`; the standard hooks collect WebView2 interop DLLs
  and `Python.Runtime.dll`) and excludes the unused qt/gtk/cocoa/
  android pywebview backends.
- `requirements.txt` gains `pywebview>=6.0,<7` (pulls pythonnet on
  Windows).
- **UI cleanup pass**: strip redundant subtitle text from Discover
  heading (tooltip only); replace secondary text buttons with icon-only
  ghost buttons (rebuild, timeline); remove redundant View buttons on
  trend rows — the term text is already clickable; right-panel tabs
  restyled as pill-shaped segmented control with Details disabled when
  nothing selected; compact AI-panel scope chips; denser trending rows;
  denser right-panel empty states (start-aligned, compact icon+hint).
- **Release policy: desktop-only.** The Windows desktop app (Setup
  EXE / MSI) is the only distribution target; the loopback server is
  an internal detail of the desktop runtime, never a deployment
  surface. The source run (`python app.py`) and `--no-window` remain
  for development and the test harness. Recorded as decision 0010 in
  [docs/decisions/README.md](docs/decisions/README.md).
- **Docs follow the desktop-only policy**: the pre-desktop production
  deployment runbook moved to `docs/archive/` (marked historical); the
  non-loopback `HOST` startup warning now points at `SECURITY.md`
  instead of the deployment guide; build artifacts (`build/`, `dist/`)
  removed from the working tree.

### Fixed
- **Wizard (and all views) invisible in production builds**: the view
  `@import` block in `web/src/design/app.css` sat at the bottom of the
  file after 458 lines of rules, which makes the import both illegal
  per CSS spec and unsupported by postcss-import. Vite silently dropped
  the entire block from production bundles (35KB → 51KB when fixed),
  so every view lost its per-view stylesheet. The wizard overlay lost
  `position: fixed` and rendered as an unstyled static block off-screen,
  making it look like clicking "Setup wizard" did nothing. The import
  block is now at the absolute top of `app.css` with a strong warning
  comment so it can never regress. This also restores Discover trending
  rows, bookmark/deal/digest cards, and other view-specific polish.
- **Ask AI never reopened after closing the panel**: the right panel's
  visibility lived as local state inside the panel component, where the
  sidebar's Ask AI button couldn't reach it. Visibility moved into the
  shared store (`rightOpen`/`setRightOpen`); the sidebar button and the
  mobile nav now open the panel explicitly, and `.app.hide-right`
  collapses the grid column so a hidden panel leaves no 360px dead
  column behind.
- **~300px of dead space above the AI panel's example chips**: the
  `.ai-chat` container rendered unconditionally with `flex: 1`, so with
  an empty conversation it greedily consumed the panel's height and
  pushed the examples to the bottom. It now renders only when there are
  turns (or a busy indicator) to show.
- **Right panel not flush to the window edge / resize mismatch**: the
  shell grid's third column was a fixed `var(--right-w)` (360px) while
  the drag handle resizes the panel element itself — so a resized panel
  overflowed its grid cell — and an inline `maxWidth: 50vw` capped it
  arbitrarily. The column is now `auto` (the grid follows the panel's
  actual width), the cap is removed, `#root` and `.app` span the full
  window, and `.right` gained `min-width: 280px` to match the drag
  clamp. Verified at 1280/1400/1600/1920px: the panel is flush to the
  right edge, no horizontal scrollbar, drag-resize persists, the
  close → Ask-AI reopen cycle is clean, and narrow (≤1100px) drawer
  mode is unchanged.

## [1.0.0] - 2026-11-11

First desktop release: Windows installers, a full UI/UX overhaul, and
a bilingual (EN/AR + true RTL) workspace. Schema unchanged from v9;
additive API only. Detailed release notes are published with each GitHub release.

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
