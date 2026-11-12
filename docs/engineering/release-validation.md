# Release Validation — v1.0.2

Date: 2026-11-12 · Machine: the audit environment (Ryzen 7 5800X3D,
32 GiB, Windows 11, Python 3.13.1, Node 20, SQLite 3.45.3).

Every result below is from a run executed during this pass — nothing is
copied from earlier reports. Commands and harnesses are named so the
run is reproducible.

---

## 1. Backend (pytest)

| Item | Result |
|---|---|
| Command | `python -m pytest tests -q` |
| Outcome | **300 passed, 0 failed, 0 skipped** — exit 0, ~107 s wall (collected count verified via `pytest --co`) |
| Baseline before this pass | 290 passed (same machine, pre-change) |
| New regression tests | 10 backend (sync fetch-error checkpoints ×4, AI repair path ×1, search media + limit clamps ×2, FAQ window coverage ×1, deals watermark ×2) + 2 frontend (`web/tests/v102.test.tsx`) |

Full-suite runs: one **before** any change (baseline, 290/290), one
**after all backend changes** (300/300), and one final run on the
finished tree (300/300). Targeted runs after each fix batch:
`test_sync_logic` + `test_ai_tasks` 19/19 (combined), `test_api` 14/14,
`test_faqs` 5/5, `test_deals` 13/13, `test_decisions` (all green).

Lint: `python -m ruff check .` → **All checks passed** (one B017 in a
new test found and fixed during the pass).

### Python compatibility (3.10–3.13)

CI (`.github/workflows/ci.yml`) runs the full suite on 3.10, 3.11,
3.12, 3.13 — that matrix is the supported-versions gate and is
unchanged. This pass's backend diffs were inspected for language-level
compatibility (no match statements, no 3.11+ typing, no new imports
beyond the existing baseline); local validation ran on 3.13.1. The
3.10–3.12 legs run on push.

## 2. Frontend (Vitest + tsc + production build)

| Item | Result |
|---|---|
| `npm run typecheck` | clean (strict) |
| `npm test` | **52 passed / 52** (10 files, incl. the new `web/tests/v102.test.tsx`) |
| `npm run build` | OK — 444.94 kB JS (120.66 kB gzip), 51.51 kB CSS, single chunk |
| New regression tests | 2 in `v102.test.tsx`: brief-notes reset (verified to FAIL on the unfixed code), digest evidence-focus consumption |
| Dependencies | `npm install --package-lock-only` → **0 vulnerabilities** (npm audit) |

## 3. API end-to-end (real app + mock AI provider + seeded archive)

| Item | Result |
|---|---|
| Harness | `scripts/seed_demo.py` (400 messages) → `scripts/mock_ai_server.py` (port 8124) → real `app.py` (port 8123) → `scripts/e2e_test.py` |
| Outcome | **128 passed, 0 failed** |

Covers: health/readiness, wizard credential persistence, auth-status
shape, browse/search (bilingual, filters), bookmarks + notes, saved
searches, scheduler config, Ask-AI grounding + citations + fallback,
deals extraction + confirm/correct, research briefs + citations +
staleness, watchlists + alerts + watermark backfill, digests + schedules,
FAQ discovery + gates, topic timeline citation stripping, entity
pipeline, exports (md/json), AI usage accounting, and cascade cleanup.

## 4. Desktop E2E (real `desktop.py` runtime, Playwright)

| Item | Result |
|---|---|
| Harness | `scripts/e2e_smoke_desktop.py` — isolated data dir + `.env` (`TGQ_ENV_FILE`), production build served by the real runtime |
| Outcome | **41 passed, 0 failed** — boot/health gate, wizard (typed + persisted credentials, dismiss/re-open), click-navigation across every view + Ask AI + Jobs + Settings modals, theme & language (incl. RTL) toggles, full window restart with persisted state, second-launch focus, graceful quit, and **zero console/page errors across every interaction** |

Note: the first attempt of this run was correctly refused by the
single-instance guard while a real (v1.0.1) instance was running —
incidental live validation of the guard against a real second launch.
The suite was then run with the user's instance closed.

## 5. Windows packaging (installer build + packaged app)

| Item | Result |
|---|---|
| Build | `python scripts/build_windows.py` — frontend (version-match enforced: web/package.json 1.0.2 == config 1.0.2) → PyInstaller 6.19 onedir → WiX 3.14 heat/candle/light MSI → Burn bootstrapper → SHA-256 `checksums.json` |
| Outcome | **All steps OK.** Artifacts: `TelegramQuery-Setup-x64.exe` 46,079,824 B (SHA-256 `f2929cf8…00bd1f`), `TelegramQuery-x64.msi` 45,641,512 B (SHA-256 `8abf2b6c…c8906b`), both stamped 2026-11-12, fresh v1.0.2 code |
| Packaged app | `python scripts/test_packaged_app.py` — launches `dist/TelegramQuery/TelegramQuery.exe` headless, discovers the port via `runtime.json`, polls readiness, asserts the DB lives under the data dir (never Program Files), verifies single-instance (second launch exits 0 fast), quits gracefully (`POST /api/app/quit`), and checks no orphan process remains |
| Packaged app result | **10/10 checks passed** — readiness 200 with `db=true`, version `1.0.2` matching `config.py`, archive created under the isolated data dir, nothing mutable written next to the exe, second instance exits 0 while the first runs, graceful quit exit 0 |

**Installer matrix scope note:** clean-install / upgrade-over-previous
/ repair / uninstall on a stock Windows machine with the produced MSI
and Setup EXE is the remaining manual gate (needs a clean VM and an
elevation prompt; deliberately not performed on this development
machine). The data-preservation properties that gate those flows were
validated by code + tests instead: data lives in
`%LOCALAPPDATA%\TelegramQuery` (per-user, never inside `INSTALLDIR`),
the MSI/WiX sources remove nothing outside `INSTALLDIR`, the
`UpgradeCode`s are fixed constants in `scripts/build_windows.py`,
`AllowSameVersionUpgrades` keeps rebuilt versions replacing the
installed product, and the `migration.py` import/auto-migrate paths are
covered by `tests/test_migration.py` + `tests/test_desktop.py`
(`test_data_import_into_empty_archive`).

## 6. Database migrations

**No migration in this pass** — `SCHEMA_VERSION` stays 9; the v1.0.2
fixes are code-only (an existing v1.0.1 database needs no upgrade
step). Migration tests (`tests/test_migration.py`) passed in the full
suite run, pinning fresh-DB and v5→v9 upgrade paths (indexes created,
`(date)` index replaced, FTS intact, version recorded).

## 7. Summary

| Suite | Result |
|---|---|
| Backend pytest (3.13 local; 3.10–3.13 in CI) | 300/300 |
| ruff | clean |
| Frontend typecheck | clean |
| Frontend vitest | 52/52 |
| Frontend production build | OK |
| API E2E (real app, mock provider) | 128/128 |
| Desktop E2E (real runtime, production UI) | 41/41, zero console errors |
| Installer build (frontend + PyInstaller + WiX + Burn) | OK — fresh 1.0.2 artifacts + SHA-256 checksums |
| Packaged app test (PyInstaller exe) | 10/10 |
