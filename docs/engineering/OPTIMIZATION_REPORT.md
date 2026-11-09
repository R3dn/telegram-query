# Optimization Report — v9 engineering pass

All numbers from `scripts/benchmark.py` (deterministic dataset, real app
subprocess, same machine), measured 2026-11-10. Baseline = v0.8.1 before
changes; After = v0.8.1 + the v9 engineering work. Methodology and
environment: `PERFORMANCE_BASELINE.md`.

## Summary table (500 k messages, P50 unless noted)

| Metric | Baseline | Optimized | Change |
|---|---:|---:|---:|
| /api/health | 0.82 ms | 0.82 ms | ±0 |
| /api/app/state | 20.7 ms | 22.7 ms | +10 % (noise, see §5) |
| /api/stats | 20.8 ms | 21.9 ms | +5 % (noise) |
| **/api/groups** | **149.8 ms** | **22.0 ms** | **−85 %** |
| **/api/senders** | **283.1 ms** | **147.6 ms** | **−48 %** |
| **/api/senders (3-chat filter)** | **89.4 ms** | **38.7 ms** | **−57 %** |
| /api/messages (first page) | 3.67 ms | 3.59 ms | −2 % |
| **first-page payload** | **22.7 KB** | **18.0 KB** | **−21 %** |
| /api/message/{id} | 2.2 ms | 2.3 ms | ±0 |
| **/api/message/{id}/context** | **13.9 ms** | **3.0 ms** | **−78 %** |
| /api/search (Arabic, ~9 % hit rate) | 149.5 ms | 142.4 ms | −5 % |
| /api/search (bilingual OR) | 189.9 ms | 179.3 ms | −6 % |
| /api/search (3-chat scope) | 127.0 ms | 123.7 ms | −3 % |
| /api/search (rare term) | 29.0 ms | 28.0 ms | −3 % |
| browse, 30 keyset pages | 121.4 ms | 114.0 ms | −6 % (HTTP-bound) |
| **DB: browse first page** | 0.19 ms | 0.15 ms | −21 % |
| **DB: browse deep (30 pages)** | **13.4 ms** | **4.8 ms** | **−64 %** |
| **DB: conversation replies** | **11.4 ms** | **0.01 ms** | **−99.9 %** |
| **DB: groups aggregate** | **145.4 ms** | **18.0 ms** | **−88 %** |
| **DB: senders (all/filtered)** | 275 / 110 ms | 145 / 31 ms | −47 % / −71 % |
| Request throughput (8 workers, mixed) | 82.7 req/s | 87.3 req/s | +6 % |
| Server RSS after sustained load | 117.1 MB | 121.5 MB | +4 MB (page cache) |
| **Ingestion, 50 k archive** | 17,077 msg/s | 15,605 msg/s | **−9 %** |
| **Ingestion, 500 k archive** | 9,667 msg/s | 3,372 msg/s | **−65 %** (see §4) |
| Ingestion rescan (unchanged text) | 4 stmts + 2 FTS ops/row | 3 stmts + 0 FTS ops/row | no FTS churn |
| Frontend bundle (gzip) | 84.92 kB | 85.03 kB | +0.3 % (AbortController) |

**Not measured** (no provider available on this machine): end-to-end AI
ask latency, Telegram network throughput. Isolated and measured instead:
AI client construction was per-ask (now cached process-wide), and the ask
pipeline issued one FTS search **per tracked chat per attempt** (now one
query per attempt via `search_diverse`).

## 1. What was implemented

| # | Change | Files | Evidence |
|---|---|---|---|
| 1 | **Composite keyset index** `(date, chat_id, msg_id)` replacing the bare `(date)` index + **row-value cursor** `(date,chat_id,msg_id) < (?, ?, ?)` | `db.py` | deep pages 760 ms (OR-form on composite) → 0.08 ms; result-identity verified |
| 2 | **Search restructure**: rank + all filters in a subquery, LIMIT, then display joins | `db.py:search` | high-hit OR query 201.9 → ~185 ms; identical result sets pinned by tests |
| 3 | **`search_diverse`**: one ranked window-function query replaces N per-chat FTS searches (Ask-AI retrieval) | `db.py`, `ai.py` | 10 chats → 1 query per attempt instead of 10 (up to 30/ask saved) |
| 4 | **`idx(chat_id, sender_name)`** | `db.py` (v9) | senders 275→145 ms (all), 110→31 ms (filtered); a bare `(sender_name)` index was **rejected**: it made the filtered case 1.8 s (6.6× worse) |
| 5 | **`idx(chat_id, reply_to)`** + planner stats | `db.py` (v9) | conversation replies 10.6 → 0.01 ms after ANALYZE |
| 6 | **Groups correlated subqueries** instead of JOIN+GROUP BY over the archive | `api/archive.py` | 149.8 → 22.0 ms; empty-chat and count semantics pinned by tests |
| 7 | **ANALYZE maintenance** (`analyze_if_stale`, post-sync hook, doubling threshold) | `db.py`, `app.py` | fixes stats-dependent plans; 0.33 s at 500 k, amortized |
| 8 | **Browse payload**: `text_norm` dropped (no consumer anywhere) | `db.py`, `digests.py` | −21 % payload per feed page |
| 9 | **Ingest fast path**: `INSERT … ON CONFLICT DO NOTHING` + rowcount, FTS maintenance only when text actually changed | `db.py` | new rows: 2 stmts (was 3); rescans: zero FTS churn (FTS row count stays exactly N — test-pinned) |
| 10 | **SQLite pragmas**: WAL + `synchronous=NORMAL` + 8 MB `cache_size` | `db.py` | no measurable change on this NVMe (helps where fsync is real); standard WAL pairing |
| 11 | **Cached AI client** keyed on (key, base_url), invalidated on wizard config change; old client closed | `ai.py` | per-ask/per-attempt construction + connection setup eliminated |
| 12 | **Provider concurrency guard** (`TGQ_AI_MAX_CONCURRENCY`, default 4; honest 503 when saturated) | `ai.py`, `ai_tasks.py`, `api/ai.py` | protects the 40-thread request pool from 90 s-timeout pile-ups; test-pinned |
| 13 | **Real token usage** for the ask pipeline (was `None` even when the provider reports usage) | `ai.py` | cost visibility for the most-used AI path |
| 14 | **Sync failure honesty**: all-chats-failed sync now fails the job (scheduler stops recording bogus success) | `sync.py` | test-pinned |
| 15 | **Readiness endpoint** `/api/health/ready` (DB check; optional deps informational) | `api/general.py` | liveness `/api/health` stays dependency-free |
| 16 | **Graceful shutdown**: cancel running job at checkpoint, ≤5 s wait, clean module state for the next instance | `app.py`, `scheduler.py` | restart-safe; found and fixed a shutdown-state leak (§6) |
| 17 | **Static asset caching** (`immutable` for hashed `/assets`, `no-cache` index) + `nosniff`/`X-Frame-Options`/`Referrer-Policy` | `app.py` | repeat loads skip re-downloading 300 kB |
| 18 | **Non-loopback bind warning** at startup | `app.py` | the no-auth posture is never silent |
| 19 | **CLI sync guard**: refuses to run beside a live app (session is one SQLite file) unless `--force` | `sync.py` | prevents the two-process session race |
| 20 | **Frontend**: `AbortController` cancels superseded feed/search requests; senders fetch debounced 250 ms | `web/src` | stale requests no longer burn a server thread + get discarded |
| 21 | **Backup script** (`scripts/backup_db.py`, online `VACUUM INTO`) + runbook | new | restore-verified by test |
| 22 | **Dependency bounds** (majors-only) after the installed set drifted to openai 3.x | `requirements*.txt` | documented, tested together |

## 2. The regression the benchmarks caught (and fixed)

First "after" run measured **browse P50 = 255 ms** (baseline 0.19 ms) —
ANALYZE'd statistics made the planner pick `idx_messages_reply` for the
browse join, turning a top-N read into a full scan + 500 k-row sort. Two
lessons applied:

1. Never ship a plan-sensitive change without re-running the benchmark.
2. The durable fix was making the ORDER BY **fully index-satisfiable**
   (composite `(date, chat_id, msg_id)`) and the cursor a **row-value
   comparison** — a plan that cannot regress regardless of statistics:
   `SEARCH m USING INDEX idx_messages_date_id ((date,chat_id,msg_id)<(?,?,?))`.

## 3. Search: what was rejected and why

A rank-only subquery (joins after LIMIT, tracked filter outside)
measures **−51 %** (201.9 → 98.4 ms) but changes semantics: untracked
chats could consume the LIMIT, returning fewer rows for archives with
untracked-but-retained messages. Rejected. The shipped restructure keeps
**every filter inside the ranked subquery** (result sets are provably
identical; tests pin untracked exclusion, filter-before-limit, bookmark
filtering, and rank order) and delivers −5-10 % on high-hit queries.
Getting the full −51 % would require denormalizing `chat_id` into the
FTS table (unindexed column) — documented as a future option, only worth
it if search latency becomes a real complaint at multi-million-row
scale.

## 4. Ingestion trade-off (deliberate, documented)

Raw DB ingestion at 500 k dropped 9.7 k → 3.4 k msg/s. Isolated
measurement: the two read-acceleration indexes cost ~28 % of raw insert
throughput at 100 k, compounding at scale as indexes exceed the page
cache. Acceptance rationale:

- Real Telegram ingestion is network/flood-bound at ~50–2,000 msg/s —
  the archive write path retains **2–17× headroom** above the fastest
  possible real sync, and backfills are checkpointed and resumable.
- The indexes buy −48…−99 % on paths users touch constantly (senders
  dropdown, conversation view, group list).
- Net position: the trade favors interactive latency over raw bulk-load
  speed, which matches this product (a personal archive you browse, not
  a bulk pipeline). Revisit only if a user genuinely backfills millions
  of messages and reports wall-clock pain (mitigation: temporarily
  `DROP INDEX idx_messages_chat_sender`, backfill, recreate + ANALYZE).

Also measured: `synchronous=NORMAL` vs `FULL` on this NVMe showed no
difference (fsync not the bottleneck); kept as the standard WAL
companion for machines where it is.

## 5. Known small regressions / non-wins (honest list)

- `/api/app/state` and `/api/stats` P50 +1–2 ms at 500 k (within run
  variance; the stats queries are aggregates over the whole archive and
  are called on job completions, not interactively).
- Search high-hit queries only improved −5-10 % (see §3) — the honest
  number, not the −51 % headline.
- Server RSS +4 MB under sustained load (the 8 MB page cache actually
  being used); flat over time — no leak.
- `senders` unfiltered stays 145 ms at 500 k (covering index scan over
  500 k entries; the earlier 38 ms experiment reading was a warm-cache
  artifact — the stable number is what's reported).

## 6. Correctness evidence

- Backend: **244 tests pass** (222 pre-existing + 22 new pinning every
  changed behavior); ruff clean.
- Frontend: **44 tests pass**, `tsc` strict clean, production build OK.
- E2E (real app + mock provider + seeded archive): **128/128 pass**.
- Search/browse result-identity: pinned by tests + a 51-row
  page-identity check between old and new cursor forms at 500 k.
- Migration: fresh-DB and v5→v9 upgrade paths tested (indexes created,
  old `(date)` index replaced, data + FTS intact, version recorded).

## 7. Remaining technical debt / next steps

1. `ai.py` ask pipeline still owns its own provider-call path (now
   shares the client, slot, and usage recording, but not the retry
   layer) — consolidating onto `ai_tasks.run_task` removes the last
   duplication. Low priority: both paths are tested.
2. In-memory job queue: queued-not-started jobs are lost on restart
   (known v0.8 limitation; a `jobs` table is the v0.10 plan).
3. `sys.stdout` job-log capture is process-wide; prints from other
   threads during a job land in that job's log (cosmetic; documented).
4. Exports (`export_deals`/`export_decisions`) still do per-row source
   queries; bounded by record counts, untouched (no measured pain).
5. Optional: denormalize `chat_id` into the FTS table for the full
   −51 % search path (§3) if ever justified by scale.
6. Frontend virtualization remains deliberately unimplemented — the
   3 000-card cap bounds the DOM; revisit only with profiling evidence
   from a real browser (not measurable in this environment).
