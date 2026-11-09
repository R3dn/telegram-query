# Performance Baseline — Telegram Query v0.8.1

Measured 2026-11-10, **before any optimization**, with the repeatable
harness `scripts/benchmark.py` (added as part of this work; dataset and
methodology described below). The "after" numbers live in
`OPTIMIZATION_REPORT.md` and were produced with the same harness on the
same machine, same seed, same scenarios.

---

## 1. Benchmark environment

| Item | Value |
|---|---|
| OS | Windows 11 (win32) |
| CPU | AMD Ryzen 7 5800X3D — 8 cores / 16 threads |
| RAM | 32 GiB |
| Disk | NVMe SSD |
| Python | 3.13.1 |
| SQLite | 3.45.3 (bundled with Python) |
| Server | fastapi 0.141.1 / uvicorn 0.52.1, single process (`python app.py`), Host 127.0.0.1 |
| Client | httpx 0.28.1, keep-alive connection pool |
| Frontend build | vite 6.4.5, production `npm run build` |

## 2. Methodology

- **Dataset**: deterministic (fixed RNG seed) synthetic archive — 10
  tracked chats (2 channels, 8 groups incl. Arabic), ~200 distinct
  senders, dates spread over 2 years, 10 % media, 15 % reply threads,
  bilingual templates with known term frequencies, plus a rare term in
  0.4 % of messages. Seeded through the **real** `db.upsert_message`
  path with commit-every-200 (mirrors the sync loop), so seeding time
  *is* the ingestion measurement.
- **Sizes**: 5 k / 50 k / 500 k messages. 500 k is the "large archive"
  scenario (~254 MiB DB); 5 k is demo-sized.
- **DB bench**: in-process `sqlite3` against the seeded file,
  60 samples, 3 warmups, P50/P95/P99.
- **API bench**: real `app.py` subprocess on the seeded DB, 100
  sequential requests per endpoint (5 warmups), then a mixed
  browse+search concurrency phase (8 workers × 12 s). AI endpoints
  excluded (require a provider) — AI-path behavior was measured
  separately at the client-construction level (§6).
- Each reported number is from a full run; repeated runs agreed within
  ±5 % on P50s (two 500 k API runs recorded; e.g. `senders` 283.1 vs
  281.5 ms).

## 3. Ingestion (through the real upsert path)

| Dataset | msgs/s | seed time | DB size |
|---|---:|---:|---:|
| 5 000 | 19 050 | 0.26 s | 3.4 MB |
| 50 000 | 17 077 | 2.93 s | 27 MB |
| 500 000 | 9 667 | 51.7 s | 254 MB |

Ingestion degrades ~2× from 50 k → 500 k (index growth + random date
insertion across a 2-year span). Real Telegram sync is network-bound
(fewer than ~200 msg/s), so the DB write path is only the bottleneck
during backfill catch-ups and re-indexes.

## 4. Database-level query latency (P50, ms; 60 samples)

| Query | 5 k | 50 k | 500 k |
|---|---:|---:|---:|
| browse first page (50 rows) | 0.18 | 0.19 | 0.19 |
| browse deep (30 pages total) | 7.4 | 7.6 | 13.4 |
| search common EN ("recipe") | 0.03* | 0.03* | 0.04* |
| search Arabic ("القهوة") | 1.5 | 14.9 | **151.6** |
| search bilingual OR ("offer\|عرض") | 2.1 | 19.9 | **206.2** |
| search rare term | 0.6 | 2.3 | 23.7 |
| senders (all chats) | 1.5 | 22.5 | **275.0** |
| senders (3-chat filter) | — | — | 109.6** |
| groups aggregate | 0.7 | 13.9 | **145.4** |
| stats (4 aggregates) | 0.14 | 1.2 | 18.5 |
| conversation around a message | 0.10 | 0.5 | **12.0** |

\* "recipe" matches are rare in the synthetic pool — treat as a
low-selectivity search; the Arabic term (~9 % of messages) and the
bilingual OR are the realistic high-hit searches.
\** from the targeted experiment run (§7).

**EXPLAIN QUERY PLAN (500 k, before):**

- browse: `SCAN m USING INDEX sqlite_autoindex_messages_1` + `USE TEMP
  B-TREE FOR ORDER BY` — full index scan + sort per page (fast only
  because SQLite streams it well; not O(page)).
- senders: `SCAN messages` + two TEMP B-TREEs — full table scan, no
  sender index.
- groups: `SCAN c` + per-chat PK search + row loads for `MAX(date)`.
- conversation replies: `SEARCH m USING INDEX sqlite_autoindex_messages_1
  (chat_id=?)` — scans the whole chat to find replies (no reply_to index;
  planner stats absent).
- search (OR query): FTS `SCAN messages_fts VIRTUAL TABLE INDEX 0:M1`,
  then **PK lookups into messages + chats + bookmarks for every match**
  (≈45 k matches) before `ORDER BY rank LIMIT 200`.

## 5. HTTP API latency (P50 / P95 / P99, ms; 100 samples)

### 500 k messages

| Endpoint | P50 | P95 | P99 | payload |
|---|---:|---:|---:|---:|
| GET /api/health | 0.8 | 0.9 | 1.1 | 29 B |
| GET /api/app/state | 20.7 | 22.0 | 25.7 | 282 B |
| GET /api/stats | 20.8 | 21.8 | 24.9 | 125 B |
| GET /api/groups | **149.8** | 166.9 | 176.6 | 1.8 KB |
| GET /api/senders | **283.1** | 323.9 | 341.8 | 8.4 KB |
| GET /api/senders (3 chats) | **89.4** | 98.3 | 107.6 | 8.2 KB |
| GET /api/messages (first page) | 3.7 | 4.0 | 4.5 | **22.7 KB** |
| GET /api/messages (30 pages) | 121.4 (total) | — | — | — |
| GET /api/message/{id} | 2.2 | 2.4 | 3.1 | 355 B |
| GET /api/message/{id}/context | **13.9** | 17.6 | 19.2 | 11.5 KB |
| GET /api/search?q=recipe | 42.7 | 50.0 | 54.7 | 73.8 KB |
| GET /api/search?q=القهوة | **149.5** | 163.1 | 173.6 | 75.3 KB |
| GET /api/search?q=offer\|عرض | **189.9** | 203.2 | 218.8 | 72.3 KB |
| GET /api/search (3-chat scope) | **127.0** | 142.3 | 144.4 | 72.3 KB |
| GET /api/search (rare term) | 29.0 | 31.9 | 36.7 | 79.3 KB |

### 50 k messages (P50)

| Endpoint | P50 | P95 |
|---|---:|---:|
| /api/app/state | 4.2 | — |
| /api/stats | 4.1 | — |
| /api/groups | 16.2 | — |
| /api/senders | 28.9 | — |
| /api/messages first page | 3.6 | — |
| /api/search?q=recipe | 10.6 | — |
| /api/search?q=القهوة | 20.0 | — |
| /api/search?q=offer\|عرض | 24.2 | — |
| /api/search (3-chat scope) | 18.3 | — |

### Concurrency & resources (mixed browse+search, 8 workers, 12 s)

| Metric | 50 k | 500 k |
|---|---:|---:|
| Throughput | 306.5 req/s | **82.7 req/s** |
| Server RSS after run | 121.4 MB | 117.1 MB |

At 500 k the mix includes two ~150-200 ms searches, so 8 workers
saturate; the server stays responsive (browse P50 unchanged under
load), and RSS is flat (~112 → 117 MB), i.e. **no memory leak** during
sustained load.

## 6. AI request path (client construction, provider not available)

No AI provider is configured on this machine, so **end-to-end AI
latency was not measured** — stating that explicitly instead of
inventing numbers. Measured instead (relevant because the harness
isolates it):

- `ai.get_client()` builds a **new `OpenAI` client (new httpx pool)
  on every ask** (ai.py:70-75), and `ai_tasks._call_with_retry`
  rebuilds it **per attempt** (ai_tasks.py:111). Against any remote
  provider this pays TCP+TLS setup per request; against localhost it
  is ~1-2 ms of pure construction overhead.
- The ask pipeline issues up to **1 FTS query per tracked chat per
  attempt** (`_search_diverse`, ai.py:133-159) — with the benchmark's
  10 chats that is up to 30 FTS queries per ask before the provider
  even answers.

## 7. Targeted experiments (root causes, 500 k dataset)

| Experiment | Before | After | Root cause |
|---|---:|---:|---|
| Search: rank in subquery, joins after LIMIT | 201.9 ms | 98.4 ms | joins/bookmarks probes for every one of ~45 k matches |
| Groups: correlated subqueries instead of JOIN+GROUP BY | 111.1 ms | 15.7 ms | MAX(date) via index seek instead of per-chat row loads |
| `idx(chat_id, sender_name)` on senders | 272.6 ms | 38.3 ms (unfiltered) / 42.6 ms (3-chat filter) | index-only scan, no row loads |
| `idx(sender_name)` on senders (rejected) | 272.6 | 37.1 unfiltered but **1 819 ms filtered** | planner probes rows for the chat filter — 6.6× worse where it matters |
| `idx(chat_id, reply_to)` + `ANALYZE` on conversation replies | 10.6 ms | 0.01 ms | reply lookup used a whole-chat PK scan; ANALYZE cost at 500 k: **0.33 s** |
| `ANALYZE` runtime at 500 k | — | 0.33 s | cheap enough for post-sync maintenance |

## 8. Frontend

- **Production bundle**: `index-*.js` 299.89 kB (gzip 84.92 kB),
  `index-*.css` 29.70 kB (gzip 6.21 kB), 57 modules — one JS chunk, no
  route splitting.
- **First feed page payload**: 22.7 KB JSON (50 messages) — includes
  `text_norm`, doubling the size vs. what the UI renders (§ audit 5.2).
- **Request behavior (static analysis of web/src)**: initial load fires
  3 GETs (state, groups, job status) + senders per selection change +
  saved searches; job polling at 1.2 s only while jobs run. Search and
  filter changes do **not** abort in-flight requests (stale requests
  still consume a server threadpool thread).
- **Rendering**: feed caps at 3 000 cards before "narrow your filters";
  no virtualization.
- **Not measured (browser unavailable in this environment)**: initial
  paint/LCP, component render counts, long-task breakdown, heap during
  extended sessions. Bundle size, payload size, and request counts above
  are the objective frontend metrics available; the render-cap analysis
  is from code. `scripts/benchmark.py` can be re-run on a machine with
  a browser for visual regression if ever needed.

## 9. Bottleneck ranking (drives the optimization plan)

1. **Search joins before rank** — every high-hit search joins 3 tables
   per match (151-206 ms at 500 k). Fix: rank in subquery, join after
   LIMIT (−51 % measured on the OR query).
2. **`senders` full scan** — 275 ms on every group-selection change;
   called constantly by the UI. Fix: `idx(chat_id, sender_name)`
   (−86 % measured).
3. **`groups` aggregate row loads** — 150 ms after every job
   completion. Fix: correlated subqueries (−86 % measured).
4. **conversation reply scan** — 11 ms of the 14 ms context endpoint.
   Fix: `idx(chat_id, reply_to)` + planner stats (−99.9 % measured).
5. **browse payload** — `text_norm` doubles feed bytes (22.7 KB/page).
   Fix: drop from the SELECT (no consumer).
6. **Planner statistics** — several bad plans (reply scan, groups) come
   from missing `ANALYZE`; 0.33 s at 500 k → cheap post-sync hook.
7. **ingestion at scale** — 9.7 k msg/s at 500 k; `synchronous=FULL`
   fsyncs every commit batch. Fix candidate: WAL `synchronous=NORMAL`
   (safe for this app's resumable, idempotent ingest).
8. **AI client churn + N+1 diverse search** — per-ask client rebuild
   and up to N-chats × attempts FTS queries.

**Not bottlenecks (verified, leave alone):** browse pagination
(0.19 ms/page at any size), message one (PK lookup), stats at ≤50 k,
health, WAL checkpointing, memory (flat RSS under sustained load).
