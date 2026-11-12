# Performance Report — v1.0.2 engineering pass

Measured 2026-11-12 with `scripts/benchmark.py` (deterministic dataset,
real ingestion path, real app subprocess). This pass is primarily a
**correctness** release; the performance work here is *verification*
that the v9 optimizations still hold and that the v1.0.2 fixes are
inert on the hot paths, plus honest measurement of the current machine.

---

## 1. Environment

| Item | Value |
|---|---|
| OS | Windows 11 (win32) |
| CPU | AMD Ryzen 7 5800X3D — 8c/16t (High performance plan, 3.4 GHz) |
| RAM | 32 GiB |
| Disk | NVMe SSD |
| Python | 3.13.1 · SQLite 3.45.3 |
| App | fastapi 0.141.1 / uvicorn 0.52.1, `python app.py` on 127.0.0.1 |
| Dataset | the harness's deterministic 500 000-message archive (283 MiB) |

**Machine-load limitation (documented per the audit rules):** during
both full benchmark runs the machine carried ~60 % background CPU load
from unrelated processes (verified via perf counters mid-run). Absolute
numbers are therefore **not comparable 1:1 with the v9 report measured
on an idle machine** — everything reads ~40-50 % slower at equal code.
Two consecutive runs agreed within ±5-10 % on P50s (e.g. DB senders
216.4 vs 214.4 ms, groups 30.2 vs 26.9 ms, API groups 34.5 vs 33.8 ms),
so the measurements are internally reproducible; the load explains the
offset from the documented baseline. Where a load-independent
statement is needed, the EXPLAIN QUERY PLAN output and the A/B guard
micro-benchmarks (§3) provide it.

## 2. Query plans: the v9 optimizations are intact

EXPLAIN QUERY PLAN on the 500k dataset, this pass (SQLite 3.45.3):

- **browse** — `SCAN m USING INDEX idx_messages_date_id` + PK seek on
  `chats` (BLOOM filter): the composite keyset index drives the page
  walk exactly as documented in v9.
- **senders** — `SCAN messages USING COVERING INDEX
  idx_messages_chat_sender`: index-only, no row loads.
- **groups** — correlated scalar subqueries resolving through the
  covering indexes `idx_messages_reply`/`idx_messages_chat_date` for
  `COUNT`/`MAX(date)` (no per-row loads).

These are the same plans the v9 report recorded; nothing this pass
changed regressed index selection.

## 3. v1.0.2 changes vs. the hot paths (A/B evidence)

The only v1.0.2 changes that touch benchmarked code paths are two
parameter guards: `db.browse` clamps `limit` (`max(1, limit)`) and
`db.search` gained a `media` branch. A/B micro-benchmark on the seeded
500k DB, interleaved rounds to cancel load drift (30 samples × 3
rounds each):

| Query | mean (ms) | round spread | verdict |
|---|---:|---:|---|
| browse first page (clamp active) | 0.170 | 0.008 | matches the documented v9 idle-machine 0.15 ms — the clamp is unmeasurable |
| browse, negative limit (clamp path) | 0.014 | 0.003 | new honest behavior (was a confusing `LIMIT 0` empty page) |
| search common EN (media branch present, unused) | 53.1 | 0.99 | same range as the historical search-common readings |
| search common EN with media=1 | 42.8 | 4.36 | new capability; strictly narrower result set |

All other v1.0.2 changes (sync error checkpointing, watermark
semantics, FAQ window, AI repair, frontend) execute outside every
benchmarked path.

## 4. Full 500k benchmark (both runs, current machine)

### Database level (P50, ms)

| Query | run 1 | run 2 | v9 doc (idle machine) |
|---|---:|---:|---:|
| browse first page | 0.27 | 0.25 | 0.15 |
| browse deep (30 pages) | 8.22 | 6.52 | 4.8 |
| search common EN | 61.1 | 59.3 | ~42 (API, low-hit) |
| search Arabic (~9 % hit) | 217.7 | 232.8 | ~142 |
| search bilingual OR | 311.6 | 295.2 | ~179 |
| search filtered (3 chats) | 193.4 | 198.2 | ~124 |
| search rare term | 37.0 | 38.1 | 28.0 |
| senders (all) | 216.3 | 214.4 | 145 |
| senders (3-chat filter) | 45.4 | 45.1 | 38.7 |
| groups aggregate | 30.2 | 26.9 | 22.0 |
| stats (4 aggregates) | 25.3 | 27.0 | 21.9 |
| conversation around a message | 0.19 | 0.13 | 3.0 |

### HTTP API (P50, ms; 100 samples, run 2)

| Endpoint | P50 | P95 | payload |
|---|---:|---:|---:|
| GET /api/health | 1.04 | 1.32 | 29 B |
| GET /api/app/state | 36.3 | 43.3 | 303 B |
| GET /api/stats | 33.8 | 42.8 | 125 B |
| GET /api/groups | 33.8 | 40.4 | 1.8 KB |
| GET /api/senders | 217.3 | 270.0 | 8.4 KB |
| GET /api/senders (3 chats) | 56.7 | 67.9 | 8.2 KB |
| GET /api/messages (first page) | 5.01 | 6.58 | 18.0 KB |
| GET /api/messages (30 keyset pages) | 167.8 (total) | — | — |
| GET /api/message/{id} | 3.25 | 4.34 | 355 B |
| GET /api/message/{id}/context | 4.54 | 5.56 | 11.5 KB |
| GET /api/search?q=recipe | 68.7 | 91.4 | 73.8 KB |
| GET /api/search?q=القهوة | 233.2 | 252.7 | 75.3 KB |
| GET /api/search?q=offer\|عرض | 283.4 | 326.0 | 72.3 KB |
| GET /api/search (3-chat scope) | 198.9 | 245.4 | 72.3 KB |
| GET /api/search (rare term) | 46.3 | 61.0 | 79.3 KB |

### Concurrency & resources (8 workers, mixed browse+search, 12 s)

| Metric | run 1 | run 2 | v9 doc |
|---|---:|---:|---:|
| Throughput | 46.3 req/s | 45.6 req/s | 87.3 req/s |
| Server RSS before → after | 111.1 → 122.4 MB | 111.3 → 120.8 MB | 121.5 MB |

RSS is flat and matches the documented figure (the mix contains two
~200-300 ms searches under 60 % background load, hence the lower
throughput). No memory leak under sustained load.

## 5. Frontend

- Production bundle before this pass: 442.48 kB JS (119.96 kB gzip).
  After the v1.0.2 frontend fixes: **444.94 kB (120.66 kB gzip)** —
  +2.46 kB (+0.56 %) for the sequence guards, keys, and debounces.
  Still a single chunk; no new dependencies added or removed.
- The 3 000-card render cap is retained; virtualization stays
  deliberately unimplemented (per the v9 decision — no profiling
  evidence from a real browser session justifies it).

## 6. Optimizations implemented in this pass

**None that trade correctness for speed** — and that is the finding.
The v9 pass already harvested the measured bottlenecks (composite
keyset index, search subquery restructure, covering indexes, ANALYZE
maintenance, payload trims, AI client reuse, provider concurrency
bound). This pass verified each still holds (§2) and confirmed the v1.0.2
fixes cost nothing measurable (§3). The remaining known hot spots
(unfiltered `senders` ~215 ms, high-hit Arabic search ~230 ms at 500k
under load) were already analyzed in the v9 report: the fast paths for
both were measured and **rejected** (sender denormalization and FTS
`chat_id` denormalization change semantics or write-path cost; §3 of
`OPTIMIZATION_REPORT.md`). Re-opening them without a user-facing
latency complaint would be optimization without evidence.

## 7. Regressions / limitations

1. Absolute latencies above are inflated ~40-50 % by background
   machine load (documented in §1); ratios and plans are load-stable.
2. `/api/app/state` and `/api/stats` remain aggregate-heavy (by
   design: called on job completions, not interactively).
3. Ingestion measured 2 023-2 801 msg/s under load (doc: 3 372 on the
   idle machine) — still ≥10× above real Telegram sync rates, with the
   same accepted read/write trade documented in v9.
