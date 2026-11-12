# Bug Audit — Telegram Query v1.0.1 → v1.0.2 engineering pass

Audit date: 2026-11-12 · Scope: full repository — sync engine, SQLite/FTS5
layer, search, AI task infrastructure, all API routers, React frontend,
desktop runtime, installer definitions, tests, CI.

Method: line-level review of every module, then **reproduction of every
suspected defect with a runnable scenario** (fake Telethon client, fake
provider client, real FastAPI TestClient, real SQLite files), then fix,
then a regression test in the shipped suite. Backend findings BUG-01
through BUG-08 were each reproduced by executing the failing scenario
before the fix; the frontend findings BUG-09 through BUG-16 come from
a dedicated per-component review pass (every effect, handler, and race
cross-checked against the API contract) with concrete reproduction
steps — the highest-impact one (BUG-09) is additionally machine-pinned
by a test that was verified to fail on the unfixed code.

Severity scale: **Critical** = silent data loss / archive corruption ·
**High** = broken documented behavior or crash on a reachable path ·
**Medium** = wrong results or resource misuse in realistic conditions ·
**Low** = cosmetic/robustness.

## Findings index

| ID | Severity | One-line summary | Fixed | Regression test |
|---|---|---|---|---|
| BUG-01 | Critical | Sync fetch errors advanced the watermark past unfetched messages (permanent silent archive gaps; failed backfill reported complete) | ✅ | 4 tests (`test_sync_logic.py`) |
| BUG-02 | High | `run_json_task` repair path crashed with `UnboundLocalError` on unparseable first replies | ✅ | `test_ai_tasks.py` |
| BUG-03 | Medium | Negative `limit` bypassed result caps on 7 list endpoints (unbounded responses) | ✅ | `test_api.py` |
| BUG-04 | Medium | Media filter displayed but silently ignored in search mode | ✅ | `test_api.py` |
| BUG-05 | Medium | FAQ discovery scanned the oldest end of busy windows (recent questions never seen) | ✅ | `test_faqs.py` |
| BUG-06 | Low | Right-panel layout breakpoint stale after window resizes | ✅ | frontend suite |
| BUG-07 | Low | AI chat index keys let per-turn state jump between turns | ✅ | frontend suite |
| BUG-08 | Medium | Deals watermark advanced past messages the provider never saw (lost incremental coverage) | ✅ | 2 tests (`test_deals.py`) |
| BUG-09 | High | Brief notes editor kept the previous brief's notes — saving wrote one brief's notes onto another | ✅ | `v102.test.tsx` (verified failing pre-fix) |
| BUG-10 | Medium | Conversation panel kept the previous message's thread | ✅ | frontend suite |
| BUG-11 | Medium | Editing a paused watchlist silently re-enabled it | ✅ | frontend suite |
| BUG-12 | Medium | Discover swallowed filter changes during first load; overlapping loads raced | ✅ | frontend suite |
| BUG-13 | Medium | Brief submit never engaged its busy flag (duplicate briefs) | ✅ | frontend suite |
| BUG-14 | Medium | FAQ save discarded the typed answer on failure | ✅ | frontend suite |
| BUG-15 | Medium | Evidence "View" jumps didn't focus the referenced record in 5 views | ✅ | `v102.test.tsx` + suite |
| BUG-16 | Low | 8 assorted view-level races, leaks, and dead controls | ✅ | frontend suite |

**Totals: 16 confirmed defects — 1 Critical, 2 High, 9 Medium, 4 Low
(the batch BUG-16 counts as one). All 16 fixed in this pass; 12 shipped
backend/frontend regression tests added.** Ten additional suspect areas
were investigated and cleared (below), and the pre-existing
documentation (v9 optimization and security reports) was re-verified
rather than duplicated.

---

## Confirmed and fixed in this pass

### BUG-01 · Critical — Fetch errors permanently corrupt the sync watermark

| | |
|---|---|
| Module | `sync.py` (`sync_chat`, `run_backfill`) |
| Reproduction | Fake Telethon client yields N messages newest-first, then raises `ConnectionError` mid-iteration. Run `sync_chat(full=True)` (scenario A) and `sync_chat()` incremental over a chat synced to id 900 with 300 new messages on "Telegram" (scenario B). |
| Root cause | Messages are fetched **newest-first**. The generic `except` handler unconditionally ran `db.update_sync_state(conn, chat_id, newest_id)` + `conn.commit()`, which (a) commits the partial batch and (b) advances `chats.last_msg_id` to the newest message **past the unfetched middle of the range**. For a fresh backfill that died before its first 500-message checkpoint, `backfill_floor` stayed `0` ("backfill complete") while only the first N messages existed. |
| Observed (before fix) | Scenario A: 100 of 1200 messages stored, `last_msg_id=1200`, `backfill_floor=0`, `stats.pending_backfills = 0` → the archive is silently 92 % empty and **no future sync ever repairs it** (incremental only fetches > 1200; `--full` is never auto-run). Scenario B: ids 1101–1200 stored, watermark advanced to 1200 → ids 901–1100 are **never fetched by any future incremental sync** (permanent gap). A later `--days` rescan heals only a 3-day window. |
| Fix | `sync_chat` tracks the fetch phase (`scan`/`inc`/`backfill`) and the oldest id the backfill actually stored (`backfill_seen`, shared with `run_backfill`). On a fetch error: a **backfill** checkpoints `set_backfill_progress(newest_id, backfill_seen)` — exactly what the cancel path already did — (keeping the previous floor when nothing was stored); a **scan/incremental** fetch keeps the pre-run watermark (`newest_id = min_id`) so the next sync re-walks the range and closes the gap with harmless `ON CONFLICT DO NOTHING` duplicates. |
| Regression tests | `tests/test_sync_logic.py::test_backfill_error_checkpoints_and_resumes`, `…::test_backfill_error_before_any_message_keeps_the_old_floor`, `…::test_incremental_error_keeps_the_pre_run_watermark`, `…::test_days_rescan_error_keeps_the_pre_run_watermark` (4 tests; both scenarios re-run to full repair). |
| Remaining risk | An error *after* the final commit but before `set_backfill_progress(floor=0)` still resumes below the last checkpoint on the next sync (idempotent re-fetch, no loss). Telethon errors raised outside iteration (e.g. `get_entity`) were already handled. |

### BUG-02 · High — `run_json_task` repair path crashes with `UnboundLocalError`

| | |
|---|---|
| Module | `ai_tasks.py` (`run_json_task`) |
| Reproduction | Provider returns unparseable text on attempt 1 with a `repair_system` prompt supplied; second response valid. |
| Root cause | `err` is only bound inside `if parsed is not None: ok, err = validate(parsed)`. When the first reply is not JSON at all, the repair-prompt f-string reads the unbound local. |
| Observed (before fix) | `UnboundLocalError: cannot access local variable 'err'…` — the documented "ONE repair attempt" instead produced a hard crash on the only path that needs the repair most (completely malformed output). Latent in v1.0.1 because no shipped caller passed `repair_system`; it is public API (`run_json_task(..., repair_system=…)`) and any feature adopting it would have hit the crash. |
| Fix | Initialize `err = None` before the attempt loop. |
| Regression test | `tests/test_ai_tasks.py::test_run_json_task_repair_prompt_on_unparseable_reply` (also pins that the repair call receives the repair system prompt and an honest "not valid JSON" problem description). |
| Remaining risk | None identified. |

### BUG-03 · Medium — Negative `limit` bypassed every result cap (unbounded responses)

| | |
|---|---|
| Modules | `api/archive.py`, `api/bookmarks.py`, `api/deals.py`, `api/decisions.py`, `api/digests.py`, `api/faqs.py`, `api/monitor.py`, `db.browse` |
| Reproduction | Seed 1500 messages; `GET /api/search?q=hello&limit=-1` returned **1500 rows** (cap was 500). `GET /api/messages?limit=-1` returned an empty page (`limit+1 == 0` → `LIMIT 0`), silently wrong in the other direction. |
| Root cause | Endpoints clamped only the upper bound (`min(limit, N)`); SQLite treats a negative `LIMIT` as *unlimited*. `entities.py`/`discover.py` already used the correct `max(1, min(...))` — the pattern was simply not applied everywhere. |
| Fix | `max(1, min(limit, N))` at all list endpoints + defense-in-depth clamp in `db.browse` (whose `limit + 1` arithmetic made negatives extra confusing). |
| Regression test | `tests/test_api.py::test_search_rejects_negative_limits` (search keeps the cap; browse no longer returns an empty page). |
| Remaining risk | Not a security boundary (loopback + host guard), but it let one request serialize the entire archive. |

### BUG-04 · Medium — The media filter was displayed in search mode but silently ignored

| | |
|---|---|
| Modules | `db.search`, `api/archive.py:/api/search`, `web/src/api/client.ts`, `web/src/state/store.tsx` |
| Reproduction | The FilterBar (rendered in both browse and search modes) offers the "with images / text only" dropdown; the chip renders as active in search mode, but `/api/search` had no `media` parameter — `db.search` did not support it. |
| Root cause | The search pipeline predates the media filter; the FilterBar never hid the control in search mode, and the store never forwarded `filters.media` on the search branch. |
| Fix | Added `media` to `db.search` (same inner-subquery filter as the other row-level filters), `/api/search` (with strict 0/1 validation — an invalid value is an honest 400, never a silent filter drop; `/api/messages` validated identically), the API client, and the store's search branch. |
| Regression tests | `tests/test_api.py::test_search_media_filter` (media=1/0 select the right rows; media=2 → 400) — behavior now consistent with browse mode and saved searches that carry a `media` field. |
| Remaining risk | None; the filter runs inside the ranked subquery so the LIMIT semantics are unchanged. |

### BUG-05 · Medium — FAQ discovery scanned the oldest end of a busy window

| | |
|---|---|
| Module | `faq.py::discover` |
| Reproduction | Seed 1100 non-question messages plus a recurring question pair at the **newest** end of a 90-day window (the run's 1000-message cap is exceeded). |
| Root cause | `db.browse(..., limit=1000, sort="asc")` read the **oldest** 1000 rows of the window. Any archive producing more than ~11 messages/day silently never scanned recent questions — exactly the ones the feature exists to find (and the radar's `source_questions`/`first_seen` evidence skewed old). |
| Fix | Read the window **newest-first** (`sort="desc"`), then re-sort the filtered question occurrences oldest-first so `first_seen` and the display-question semantics are unchanged. |
| Regression test | `tests/test_faqs.py::test_discover_covers_the_newest_end_of_a_busy_window`. |
| Remaining risk | Windows with > 1000 *questions* still truncate at the cap; acceptable (bounded job) and now truncating from the end that recurs least. |

### BUG-06 · Low — The right-panel responsive flag never reacted to window resizes

| | |
|---|---|
| Module | `web/src/App.tsx::RightPanel` |
| Root cause | `const narrow = window.matchMedia("(max-width: 1100px)").matches` was evaluated once per render with no listener. In the resizable desktop window, crossing the 1100px breakpoint without an unrelated re-render left the panel in the wrong mode (and the mobile-nav class toggles stale). |
| Fix | `narrow` is now component state subscribed to the `MediaQueryList` `change` event. |
| Regression tests | Frontend suite + typecheck (render behavior unchanged; `npm test` 50/50). |

### BUG-07 · Low — AI chat turns used index keys on a front-trimming list

| | |
|---|---|
| Module | `web/src/components/AiPanel.tsx` |
| Root cause | `chat.map((turn, i) => <TurnView key={i}…>)` — the persisted chat is capped at 50 turns and trimmed **from the front**, so index keys shift and per-turn state (the `exporting` flag) can attach to a different turn after a trim. |
| Fix | Stable `key={turn.at}` (the turn's creation timestamp). |
| Regression tests | Frontend suite (50/50) + typecheck. |

### BUG-08 · Medium — Deals incremental watermark advanced past messages the provider never saw

| | |
|---|---|
| Module | `deals.py::extract` |
| Reproduction | Incremental extraction with candidates above the watermark and a provider that fails mid-run (`ConnectionError` from the client). |
| Root cause | `_advance_watermark` ran **before** the AI batches, so a provider failure mid-run left the watermark past messages that were never extracted — silently lost incremental coverage (recoverable only by a manual scoped backfill job). `decisions.py` already had the correct advance-on-success semantics; `deals.py` was the divergent copy. |
| Fix | The watermark now advances (a) when the candidate window is empty (the common no-new-deals case must not re-scan forever) and (b) after **every** batch succeeded. A failed run heals on the next sync, and unchanged batches are fingerprint-cache hits, so retries cost nothing. |
| Regression tests | `tests/test_deals.py::test_incremental_watermark_survives_provider_failure` (failure → watermark unchanged; recovery → extraction completes and advances; next run is a no-op), `…::test_incremental_watermark_advances_when_no_candidates` (empty window still advances). |
| Remaining risk | A repeatedly failing provider now re-runs candidate search per sync (bounded at 400 candidates/chat, cached batches are free) — the deliberate trade for never losing coverage. |

### BUG-09 · High — Brief notes editor kept the previous brief's notes (cross-record corruption)

| | |
|---|---|
| Module | `web/src/components/ResearchView.tsx` (`BriefDetail`) |
| Reproduction (verified) | Create two briefs → open brief A, type text in the Notes box → click brief B in the list → the notes box still shows A's text under B's question → "Save notes" persists A's text onto brief B. |
| Root cause | `BriefDetail` was rendered without a `key`; React reused the same component instance when `selected` changed, so `useState(brief.notes)` never re-initialized. |
| Fix | `key={selected.id}` remounts the detail per brief. |
| Regression test | `web/tests/v102.test.tsx` — "switching briefs resets the notes editor" (verified to **fail** on the unfixed code and pass with the fix). |
| Remaining risk | None. |

### BUG-10 · Medium — Conversation panel kept the previous message's thread

| | |
|---|---|
| Module | `web/src/components/DetailsPanel.tsx` + `ConversationBlock.tsx` |
| Reproduction | Select message A → "View conversation" → A's thread renders → select message B → B's details render but the conversation block still shows A's thread with A highlighted as the target. |
| Root cause | `ConversationBlock` keeps its fetched context in state and only resets on manual close; the component was not keyed by message. |
| Fix | `<ConversationBlock key={`${m.chat_id}:${m.msg_id}`} m={m} />` — the block resets with the selection. |

### BUG-11 · Medium — Editing a paused watchlist silently re-enabled it

| | |
|---|---|
| Module | `web/src/components/WatchView.tsx` (`WatchModal.save`) |
| Reproduction | Create a watchlist → pause it → edit (rename or add a term) → Save → the "Paused" badge disappears and the next sync starts matching again, generating unread alerts. |
| Root cause | The save body hard-coded `enabled: true` for both create and edit. |
| Fix | `enabled: w ? w.enabled : true` — edits preserve the paused state. |

### BUG-12 · Medium — Discover swallowed filter changes made during its first load, and slow loads overwrote newer ones

| | |
|---|---|
| Module | `web/src/components/DiscoverView.tsx` |
| Root causes | (a) The reload effect was guarded by `trending !== null`, so a window/group change made while the first load was in flight did nothing, and the view then showed the old window's data under the new tab. (b) `load()` had no ordering guard: two overlapping loads resolved last-writer-wins regardless of which was newer. |
| Fix | Guard removed (the mount effect was redundant with the unguarded deps effect); a load sequence counter discards superseded responses. The topic-timeline request got the same counter, and its Close button now invalidates in-flight responses (previously a response could resurrect the closed panel and enable overlapping requests). |
| Regression tests | Frontend suite + typecheck (52/52). |

### BUG-13 · Medium — Submitting a research brief never engaged its own busy flag (duplicate briefs)

| | |
|---|---|
| Module | `web/src/components/ResearchView.tsx` (`create`) |
| Root cause | `creating` derived from `jobs.running`, but nothing kicked the store's job poller after `briefCreate` — so `jobs` stayed stale-false, the button stayed enabled for the whole generation, and a second submit (double Ctrl+Enter) created a duplicate brief. |
| Fix | Local `submitting` state around the request + `refreshJobs()`/`load()` on success (the same pattern every other job-starting flow uses). |

### BUG-14 · Medium — FAQ "Save answer" discarded the typed answer when the save failed

| | |
|---|---|
| Module | `web/src/components/FaqView.tsx` |
| Root cause | `patch()` swallowed errors and always resolved; the save handler unconditionally closed the editor, so a failed save (backend restarting, provider down) lost the entire typed answer. Same pattern for "Mark outdated". |
| Fix | `patch()` returns success; the editor stays open (with the typed text) on failure. |

### BUG-15 · Medium — Evidence "View" jumped to a view but never focused the record

| | |
|---|---|
| Modules | `ResearchView`, `DigestsView`, `AlertsView`, `FaqView`, `EntityView` (consumption); `DealsView`/`DecisionsView` (filter-vs-focus edge) |
| Root cause | The Evidence Explorer sets `evidenceFocus {kind,id}` before switching views, but only Deals/Decisions consumed it; briefs opened the *newest* brief instead of the referenced one, digests/alerts/faqs/entities landed unfocused. Deals/Decisions also burned the focus when the target row was excluded by an active filter. |
| Fix | Every target view consumes and clears the focus: Research selects the brief, Digests opens the digest, Alerts switches to the tab that can contain it, FAQs fetch-all + open the referenced row, Entities open the detail; Deals/Decisions reset their row filters before expanding. |

### BUG-16 · Low — Assorted view-level races and leaks (batch fix)

| ID | Module | Defect | Fix |
|---|---|---|---|
| a | `ManageGroups.tsx` | The dialogs polling loop (`jobStatus` every 1.3 s) kept running after the modal closed, with state writes to an unmounted component | Abort flag set in the unmount effect, checked at every loop step |
| b | `ManageGroups.tsx` | "Stop current job" was an async onClick without try/catch — a failed call was an unhandled rejection with no feedback | try/catch + error toast |
| c | `EntityView.tsx` | Search fired a request per keystroke with no ordering guard (a slow older response could replace a newer one) | 250 ms debounce (the BookmarksView pattern) + sequence counter |
| d | `DealsView.tsx`, `DecisionsView.tsx` | Filter-change loads raced (debounce covered only `q`) | Sequence counters |
| e | `AlertsView` (`WatchView.tsx`) | Tab-switch loads raced | Sequence counter |
| f | `DigestsView.tsx` | `openDigest` raced (two quick clicks could open the first digest) | Sequence counter |
| g | `DigestsView.tsx` | The "New weekly schedule" dropdown choice was discarded — the modal always opened as "daily" and an unnoticed save scheduled the wrong frequency | The choice seeds the modal (`initialFreq`, keyed) |
| h | `ResearchView.tsx` | The "Open Telegram" control in citation rows was a passive `<span class="link">` — clicking it opened the in-app view instead of Telegram | stopPropagation + `window.open(tg_link)` |

All fixed in this pass; frontend suite (52 tests incl. the new `v102.test.tsx`) and strict typecheck green.

---

## Investigated and **not** a defect (validated, left unchanged)

These were suspected during the audit and explicitly cleared, so the
next pass does not re-litigate them:

1. **Backfill cancel/resume checkpoints** — `run_backfill`'s pause path
   checkpoints below the oldest fetched id and resume walks `max_id =
   floor - 1`; pinned by the existing checkpoint tests plus the new
   error-path tests.
2. **`upsert_message` FTS maintenance** — the fast path
   (`ON CONFLICT DO NOTHING` + `rowcount`) inserts exactly one FTS row
   per new message; the update path rewrites FTS entries only when
   `text_norm` changed (no churn on unchanged day-rescans; test-pinned
   in the suite).
3. **Markdown/XSS** — every `dangerouslySetInnerHTML` site renders
   through `mdToHtml`, which HTML-escapes **all** input before adding
   any markup (7 call sites verified; unit tests pin `<script>` escape).
   The citation, bold, and code substitutions can only inject
   already-escaped text.
4. **Host guard** — `_host_token` handles `host:port` and IPv6 bracket
   forms; tests cover the foreign-host 403 and loopback/TG_ALLOWED_HOSTS
   allowance. No CORS headers exist anywhere (grep-verified).
5. **Keyset pagination** — the row-value cursor
   `(date, chat_id, msg_id) < (?, ?, ?)` is a direct composite-index
   seek; the benchmark (§ performance report) shows 0.27 ms pages at
   500 k rows. No OFFSET pagination on the archive paths
   (`entity_detail` uses a bounded OFFSET over per-entity mentions,
   ≤ 100 rows — accepted).
6. **`search` vs `search_diverse` result-identity** — both rank in a
   subquery with all filters applied before the LIMIT (v9 shape);
   the new `media` filter follows the same pattern.
7. **Additive migrations** — v1→v9 reviewed line by line: every step is
   guarded (`IF NOT EXISTS`, column checks, `INSERT OR REPLACE` on
   `schema_meta`), `ANALYZE` failure is non-fatal, and no step can run
   destructively. This pass adds **no migration** (schema unchanged).
8. **Installer data preservation** — data lives in
   `%LOCALAPPDATA%\TelegramQuery`; the MSI (perMachine, Program Files)
   removes nothing outside `INSTALLDIR` on uninstall; fixed
   `UpgradeCode`s + `AllowSameVersionUpgrades` keep upgrades in-place.
   `POST /api/data/erase` is the only deleter and requires the typed
   `ERASE` token.
9. **Scheduler after Windows sleep/resume** — the loop re-reads
   `now` on every tick (30 s), so a missed due time fires one catch-up
   sync on resume and re-arms; no wall-clock math that breaks on sleep.
10. **Job-runner serialization** — one job at a time with
    dedup-by-name; the Telegram session is never used concurrently
    (the CLI refuses to run beside the live app).

## Known limitations (documented, no change in this pass)

- **`sys.stdout` job-log capture is process-wide** — prints from other
  threads during a job land in that job's log (cosmetic; queued as
  technical debt in the optimization report).
- **Queued-not-started jobs don't survive a restart** — running jobs
  checkpoint; the queue is in-memory (v0.10 plan).
- **`db.get_db` per-path initialization is not lock-guarded** — in this
  codebase `init_db()` always runs before worker threads exist
  (import time in `app.py`, before uvicorn starts), so the
  check-then-add race on `_INITIALIZED` is unreachable in shipped
  flows; noted for any future embedded usage.
- **`entities.list_entities` LIKE filter doesn't escape `%`/`_`** —
  user-typed wildcards act as wildcards (a search-semantics quirk in a
  local UI, not injection; parameters are bound).
