# Windows Desktop Stabilization Audit — Telegram Query v1.0.2 → v1.0.3

Audit date: 2026-11-12 · Scope: the complete Windows desktop lifecycle —
desktop runtime (`desktop.py`), data lifecycle (erase/import/migration),
SQLite integrity, Telegram sync integration, backend/frontend reliability,
packaging (PyInstaller + WiX), Windows-specific compatibility — with every
suspect finding **reproduced or explicitly cleared** before a fix shipped.

Method: line-level review of the desktop runtime and the data endpoints,
then **execution of every suspected defect** (real FastAPI TestClient
against a real SQLite file; real `desktop.main()` runs with the server,
dialogs, and window pieces stubbed at the exact OS boundary), then fix,
then a machine-pinned regression test in the shipped suite. The prior
v1.0.1→v1.0.2 audit (`bug-audit.md`) was re-verified rather than
duplicated: its 16 fixes and regression tests still hold (full suite
green before this pass started).

Severity scale: **Critical** = silent data loss / archive corruption ·
**High** = core functionality broken on a reachable path ·
**Medium** = wrong behavior or resource misuse in realistic conditions ·
**Low** = cosmetic/robustness.

## Findings index

| ID | Severity | One-line summary | Fixed | Regression test |
|---|---|---|---|---|
| WS-01 | High | "Erase all data" left the running app unable to serve any request (schema-less DB re-created in-process) until a restart | ✅ | `test_desktop.py::test_data_erase_recreates_a_working_empty_archive` (reproduced first) |
| WS-02 | Medium | After erase, the app kept reporting Telegram/AI as configured (credentials lived on in the process env) | ✅ | same test (`telegram_configured is False`) |
| WS-03 | Medium | Initial window (1400×900 logical) overflowed the screen on 1366×768 laptops and at 125–150 % scaling on FHD | ✅ | 5 `fit_window_size` tests (100 %, 150 %, tiny screen, no-metrics fallback) |
| WS-04 | Medium | A backend that exited during startup made the user wait the full 60 s startup timeout before any error | ✅ | `test_desktop.py::test_startup_fails_fast_when_the_backend_thread_dies` |
| WS-05 | Medium | Early startup failures (unwritable data dir, full disk, unwritable runtime file) killed the windowed exe silently — no console, no log, no dialog | ✅ | `…::test_unwritable_data_dir_shows_a_startup_dialog`, `…::test_late_startup_failure_is_reported_not_silent` |
| WS-06 | Low | First-login success toast showed an empty account name (stale render-time snapshot) | ✅ | `web/tests/onboarding.test.tsx` (verified failing pre-fix) |
| WS-07 | Medium | Test suite: 26 `with db.get_db() as conn:` blocks leaked open SQLite connections (`with conn:` commits but never closes) — the session DB stayed locked on Windows, deterministically breaking file-level tests suite-wide | ✅ | the erase regression test itself (failed in full-suite runs until the leak was fixed); all 26 wrapped in `contextlib.closing` |
| WS-08 | Medium | A second launch that found a live-but-windowless instance exited **silently** — the user's click appeared to do nothing (headless test instance, or a window that never appeared) | ✅ | 3 `focus_existing` tests (focus success stays silent; headless + unfocusable each get an honest dialog) |
| WS-09 | Low | The dev Start-Menu shortcut targeted `python.exe` — a **console** program — so every launch flashed a terminal that read exactly like a crash | ✅ | 3 `_windowed_interpreter` tests (pythonw preferred, fallback, frozen keeps the exe) |
| WS-10 | High | The shortcut's Arguments carried the script path **unquoted** — with the repo under `E:\AI Projects\...` (a space) the interpreter received `E:\AI` as the script and exited instantly: every click did nothing (flash-of-error console under python.exe, fully silent under pythonw) | ✅ | `test_shortcut_arguments_quote_paths_with_spaces` + `…::…_real_launch_with_spaces` (raw command-line launch against a space-containing script path) — reproduced live on the user's machine |

**Totals: 10 confirmed defects — 2 High, 6 Medium, 2 Low. All 10 fixed in
this pass; 18 backend + 1 frontend regression tests added.** The
investigated-and-cleared list (below) documents the areas verified
sound so the next pass does not re-litigate them.

---

## Confirmed and fixed

### WS-01 · High — "Erase all data" broke the running application

| | |
|---|---|
| Module | `api/data.py::erase_data` + `db.get_db` (schema guard) |
| Reproduction (executed) | Seed one message → `POST /api/data/erase {"confirm":"ERASE"}` → 200 → the UI reloads itself 1.5 s later (`SettingsModal.doErase`). **Observed before fix**: `GET /api/health/ready` → **503** ("archive database unavailable"), `GET /api/app/state` → **500** (`sqlite3.OperationalError: no such table: messages`), scheduler tick failing — every DB-touching request until the process restarts. |
| Root cause | `db.get_db()` runs `SCHEMA` + `_migrate` only the first time it sees a database *path* (`_INITIALIZED` set). Erase deletes the file but the guard survives; the next connection `sqlite3.connect`s a brand-new **empty** file and skips the schema. The reload-after-erase contract (the UI never restarts the process) then lands on a database with no tables. |
| Fix | `db.forget_initialized(path)` drops the one-time guard; `erase_data` calls it after the deletions, so the *very next* request rebuilds a fresh, schema-complete empty archive. Verified end-to-end: readiness 200, `/api/app/state` 200 with `messages: 0`, and `/api/search` (needs the FTS table) functional again. |
| Remaining risk | None. A queued (not running) job could start mid-erase — its connection open would make the unlink fail with an honest 409 ("may be in use") and nothing is deleted; self-healing on retry. |

### WS-02 · Medium — After erase, the app still claimed to be configured

| | |
|---|---|
| Module | `api/data.py::erase_data`, `config.update_env` |
| Root cause | The wizard persists credentials with `config.update_env`, which writes the `.env` **and** sets `os.environ`. Erase deleted the file but the in-process environment kept the credentials, so `telegram_configured` / `ai_configured` stayed true — the wizard reopened at the *login* step under an "erase everything" promise. |
| Fix | The erase action clears the app-managed credential variables (both current and legacy names) and rebuilds settings, consistent with the in-process caches it already reset (`AUTH_STATE`, `DIALOGS_CACHE`). System-level env vars (set by the user outside the app) correctly re-apply on the next launch. |

### WS-03 · Medium — The initial window overflowed small and scaled displays

| | |
|---|---|
| Modules | `desktop.py::run_app_window`, pywebview `platforms/winforms.py` |
| Root cause (verified in pywebview source) | `BrowserForm` sets `Size = (initial_width × scale, initial_height × scale)` in **physical** pixels and never clamps to the monitor. The documented 1400×900 logical default therefore measures 2100×1350 physical at 150 % — larger than a 1920×1080 screen — and exceeds 1366×768 at 100 % on both axes. The window opened clipped off-screen on exactly the configurations the task calls out (100 %, 125 %, 150 % scaling). |
| Fix | `fit_window_size()` clamps the initial size to the primary monitor's work area (`GetSystemMetrics(SM_CX/CYFULLSCREEN)`) converted back to logical pixels via the primary DPI (`GetDpiForSystem`), respecting the 960×600 minimum only when the screen allows it. Any display that fits 1400×900 keeps it unchanged; off-Windows/failed metrics keep the default. The resizable minimum stays as-is (user-driven resizes are their own choice). |

### WS-04 · Medium — Startup stall: a dead backend waited out the whole timeout

| | |
|---|---|
| Module | `desktop.py::wait_healthy` / `main` |
| Root cause | The readiness poll probed only the HTTP endpoint. Uvicorn exits on a failed bind or a startup crash (port stolen in the pick-then-bind window, `SystemExit` in `serve()`); the health probe then just times out and the user stared at nothing for the full `TGQ_STARTUP_TIMEOUT` (default 60 s) before the error dialog. |
| Fix | `wait_healthy` now takes the server thread and reports a dead thread within one poll interval; the dialog says the backend *exited during startup* and points at the log (uvicorn's own error — e.g. the bind failure — was already written there by the root logger). Regression test drives `desktop.main()` with a fake uvicorn whose `run()` exits immediately and asserts the failure is reported in ~1 s, not the configured 30 s. |

### WS-05 · Medium — Silent startup deaths of the windowed exe

| | |
|---|---|
| Module | `desktop.py::main` |
| Root cause | `configure_logging()` (first statement) and the unguarded mid-section (`write_runtime_file`, the uvicorn import, the pick_port fallback) could raise on unwritable data dirs, full disks, and broken installs. A windowed PyInstaller exe has no console, and with logging not yet configured there was neither a log line nor a dialog — the process vanished. |
| Fix | Two honest paths: (a) a logging-setup failure shows the native dialog naming the data dir and writes a crash dump to `%TEMP%\TelegramQuery-startup-error.log` (the only writable place left); (b) any unexpected later exception is logged and reported through the same dialog. The graceful-shutdown and dialog-free paths are unchanged. |

### WS-06 · Low — Login toast rendered an empty account name

| | |
|---|---|
| Module | `web/src/components/Onboarding.tsx::LoginStep.run` |
| Root cause | The success toast read `appState.auth_user` from the render-time closure — always the pre-login value, since `refreshAppState()` cannot mutate a captured snapshot. The toast said "Logged in as " with no name. |
| Fix | Read the label from the login response, which carries `user` (the same payload `api/auth.py` returns). The frontend regression test was verified to **fail** on the unfixed code. |

### WS-07 · Medium — The test suite leaked SQLite connections (Windows file locks)

| | |
|---|---|
| Modules | 26 `with db.get_db() as conn:` blocks across 10 test files |
| Reproduction (executed) | The new erase regression test passed alone but failed **deterministically in full-suite runs**: `Could not delete test.db … [WinError 32] … being used by another process`. Bisected to `test_deals.py::test_deals_api_crud`. |
| Root cause | `with sqlite3.Connection as conn:` only wraps a transaction — it **commits but never closes**. CPython frees the connection only at the next cyclic GC (reference cycles retain it), so the session database stayed open and Windows kept the file locked — breaking any file-level operation (erase, import, migration landing) unpredictably for the whole suite. Latent since the affected tests were written; harmless on POSIX (open files can be unlinked), which is why CI never caught it. |
| Fix | All 26 sites wrapped in `contextlib.closing(db.get_db())`, which closes the connection on exit. Mechanical, behavior-preserving, verified by the previously-failing combination now passing. |

### WS-08 · Medium — A second launch could exit silently ("the click does nothing")

| | |
|---|---|
| Module | `desktop.py::_surface_running_instance` (second-launch handoff) |
| Reproduction (live report) | User clicks the app; the launcher's console flashes, closes, and nothing appears — while the single-instance mutex is held by a live instance with **no window** (a headless/test instance, or one still starting past the focus deadline, or hung). |
| Root cause | `_surface_running_instance` returned quietly whenever the running instance recorded `ui=none`, or when `_focus_existing_window` found no window — treating "the window will appear later" as guaranteed. For a real desktop user this is indistinguishable from a broken app: no window, no dialog, no message. |
| Fix | The handoff now always leaves the user with something: the focused window, or an honest dialog — a headless instance gets "a test/background instance is running (port N); close it via Task Manager", an unfocusable window instance gets "still starting or not responding; close it from the notification area or Task Manager and start again". The quiet path remains for genuinely quiet callers (headless test second-launches, `quiet=True`). |
| Note | The same report exposed that the user's dev Start-Menu shortcut targeted console-mode `python.exe` (WS-09) — which is what flashed the terminal. |

### WS-09 · Low — The dev Start-Menu shortcut flashed a console on every launch

| | |
|---|---|
| Module | `desktop.py::_ensure_start_menu_shortcut` / `_windowed_interpreter` |
| Root cause | `_set_taskbar_icon` (source runs) writes a Start-Menu shortcut targeting `sys.executable` — `python.exe`, a **console** program. Every launch opened a black terminal window that closed the moment the process exited (or handed off to another instance), reading exactly like a crash, and hiding any short-lived error output. The shortcut's update check also compared against an AUMID value WSH cannot read, forcing a pointless rewrite every boot. |
| Fix | The shortcut now targets `pythonw.exe` when it exists next to the interpreter (same script, no console; `desktop.py`'s `ensure_streams()` provides devnull-backed stdio). The update check compares what WSH can actually read (target + icon), so the rewrite happens once (the python.exe → pythonw.exe migration) and then never again. Frozen apps keep their own exe as the target. |

### WS-10 · High — The shortcut's script path was unquoted: "the app won't open" on paths with spaces

| | |
|---|---|
| Module | `desktop.py::_ensure_start_menu_shortcut` / `_shortcut_arguments` |
| Reproduction (live, on the user's machine) | Clicking the Start-Menu shortcut did nothing at all. Captured by launching the shortcut verbatim: `pythonw.exe: can't open file 'E:\\AI': [Errno 2] No such file or directory`. No log entry, no crash dump — the process died before `main()` could start. |
| Root cause | `sc.Arguments = str(Path(__file__).resolve())` wrote the script path **without quotes**. Windows passes the Arguments field verbatim on the command line; the repo lives under `E:\AI Projects\Telegram_quary` — a path containing a **space** — so the interpreter received `E:\AI` as the script name, failed instantly, and exited. Under `python.exe` this flashed the error in a console for a split second (the user's original report); under `pythonw` (WS-09's fix) it became fully silent ("I can't even open it"). This is precisely the audit's "installation in directories containing spaces" scenario — latent for every user whose checkout path has a space. |
| Fix | `_shortcut_arguments()` emits the quoted path, and the end-to-end regression test launches the real interpreter through a **raw command line** (exactly how Explorer launches a shortcut) against a script whose path contains spaces, asserting it runs. The user's live shortcut was also repaired in place. |
| Note | The packaged app is unaffected (its shortcuts pass no arguments); this bug was specific to the source-run shortcut — but it is what made the app unopenable on this machine. |

---

## Investigated and **not** a defect (validated, left unchanged)

1. **Single-instance + second-launch handoff** — the named mutex,
   the runtime-file port discovery, and the 15 s `focus_existing` poll
   were re-traced against the relaunch flow; the packaged-app test
   (second instance exits 0 while the first serves) pins it against a
   real frozen build.
2. **Graceful shutdown / orphan processes** — window close, tray Exit,
   and in-app Exit all funnel into `QUIT` → uvicorn stop → FastAPI
   lifespan (job cancel at checkpoint, scheduler stop); the 20 s join
   timeout falls back to `os._exit` with committed WAL data intact
   (the `-wal` file is recovered by the next connection). The packaged
   test asserts exit code 0 and no leftover process; the desktop E2E
   asserts both quit paths.
3. **SQLite concurrency** — one process (mutex), WAL + 20 s busy
   timeout, short transactions (200-message commits), one-job-at-a-time
   runner, CLI refusal to run beside the live app. The suite's
   concurrency tests and the v1.0.2 audit conclusions were re-verified.
4. **Sync watermark / backfill checkpoints** — the v1.0.2 fixes
   (error-phase checkpointing, pre-run-watermark retention) were
   re-read against the failure matrix; the four pinned regression
   tests still pass.
5. **Migration safety** — copy-based, staging, database-last landing,
   lock with stale takeover, backup-API snapshots; `auto_migrate` is
   inert in source runs and honors explicit path overrides. Pinned by
   `test_migration.py` and `test_desktop.py`.
6. **Windows paths / Unicode** — all file I/O goes through `pathlib`
   with explicit `encoding="utf-8"`; the data dir derives from
   `%LOCALAPPDATA%`; SQLite/Telethon/logging all use wide-char or
   UTF-8-safe APIs; installer paths have no spaces issues (Program
   Files). Arabic content and usernames flow through `dir="auto"`
   rendering and UTF-8 JSON.
7. **MSI upgrade/uninstall semantics** — fixed `UpgradeCode`,
   `AllowSameVersionUpgrades`, per-machine `INSTALLDIR`-only removal:
   user data in `%LOCALAPPDATA%\TelegramQuery` survives upgrades and
   uninstall by design; the erase endpoint remains the only deleter
   (typed `ERASE` token).
8. **Exports and downloads** — filenames are built server-side from a
   fixed ASCII prefix + date; Arabic *content* is UTF-8 in the body.
   `URL.revokeObjectURL` cleanup after 30 s is intentional (WebView2
   needs the blob alive through the save dialog).
9. **Job log capture (`sys.stdout` tee)** — process-wide by design,
   cosmetic in the job log; documented as known limitation in the
   optimization report; unchanged.
10. **`_ensure_start_menu_shortcut` rewrite check** — the AUMID
    condition never matches (WSH cannot read that property), so the
    shortcut is rewritten once per boot; benign (per-user, ms-scale,
    idempotent patch), and the packaged app gets its Start-Menu
    shortcut from the MSI regardless. Left unchanged; noted here so
    the next pass does not re-investigate.
11. **Host guard / readiness split** — liveness touches nothing,
    readiness fails only on the archive; re-verified with the tests.
12. **Frontend races/leaks** — the v1.0.2 batch (BUG-12/16) covers the
    view-level races; this pass re-read the store, Feed, SearchBar,
    Modal, ManageGroups, Onboarding, and SettingsModal against the
    desktop interaction patterns (Enter/Escape, focus, modal overlay,
    polling cleanup) and found no new defects beyond WS-06.

## Verification performed (this pass)

| Suite | Result |
|---|---|
| Backend pytest (incl. 16 new tests) | **all green** (16 erase/window/startup/second-launch regressions added) |
| Frontend vitest (incl. new `onboarding.test.tsx`) | **53/53 green**, strict `tsc --noEmit` clean |
| Ruff lint | clean |
| Desktop E2E smoke (`scripts/e2e_smoke_desktop.py`, real desktop.py + real UI) | **41/41 PASS** — boot, wizard, navigation, theme/language persistence, restart, second launch, graceful quit, zero console errors |
| Packaged app (`scripts/test_packaged_app.py`, real frozen exe) | **10/10 PASS** — headless boot, port discovery, readiness payload, data-dir isolation, single instance, graceful quit, no orphans |

## Known limitations (documented, no change in this pass)

- **Erasing during the first seconds after launch can return an honest
  409**: the lifespan's background auth check opens the Telegram session
  file (a real network handshake). The erase's deletion of the session
  file retries for ~3 s, then reports "may be in use — try again". Safe
  by design (never deletes under a live handle — reproduced and
  verified that the retry succeeds and leaves a working empty archive).
- The startup window clamp uses the **primary** monitor's work area; a
  window restored onto a removed monitor is re-centered by Windows.
- The erase flow intentionally does not quit the app (the UI reloads
  into the rebuilt empty archive); the unused `quit` field in the
  response stays for future desktop-mode auto-restart.
- Queued-not-started jobs don't survive a restart (v1.0.2 limitation,
  unchanged).
- `sys.stdout` job-log capture is process-wide (cosmetic, unchanged).
