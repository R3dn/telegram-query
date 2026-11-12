# Release notes

## 1.0.3 (2026-11-12)

Windows desktop stabilization release. No schema migration — run the
installer over the old one; your archive, session, and settings survive
by design.

- **"Erase all data" now actually restarts the app cleanly**: erasing
  used to leave the running backend without a usable database — every
  view failed until the app was manually restarted — and the app kept
  claiming Telegram/AI were configured. Erase now rebuilds a fresh
  empty archive immediately and honestly reports itself as unconfigured,
  so the setup wizard reopens by itself.
- **The window fits your screen**: on 1366×768 laptops and at 125–150 %
  display scaling, the app window opened larger than the screen and was
  clipped. The initial window is now sized to your primary display's
  work area (the design size is kept whenever it fits).
- **Startup failures are reported, never silent**: if the backend
  cannot start (or the data folder is unwritable / the disk is full),
  the app now shows a clear error dialog within moments instead of
  either stalling for a minute or disappearing without a trace, and it
  writes a crash dump you can attach to a bug report.
- **Fixed: the app would not open from the Start-Menu shortcut at all**
  when the program folder contains a space in its path (the shortcut
  passed the script path unquoted, so the app exited before it could
  even show an error). If you hit this, one more click after updating
  opens normally.
- **"Clicking the app does nothing" is now impossible**: when another
  Telegram Query instance is already running but has no window to
  focus (a background/test instance, or one still starting or hung),
  a new click used to exit silently. It now either focuses the running
  window or shows a clear message explaining what's running and how to
  close it.
- The dev Start-Menu shortcut no longer flashes a console window on
  every launch (it now runs the windowed Python interpreter).
- The first-login toast now shows the account name.

Full details: `docs/engineering/windows-stabilization-audit.md` (the
complete audit: findings, fixes, and verification),
`docs/engineering/release-validation.md` (test results).

## 1.0.2 (2026-11-12)

Stability and correctness release from the full v1.0.1 engineering
audit. No schema migration — run the installer over the old one; your
archive, session, and settings survive by design.

- **Critical sync fix**: a network error mid-fetch used to advance the
  sync watermark past messages Telegram never delivered, silently
  leaving permanent gaps in the archive (and a failed first backfill
  was even recorded as complete). Backfills now checkpoint progress on
  errors exactly like the Stop button, and failed incremental fetches
  are re-walked and repaired by the next sync.
- **Search filters are honest**: the images/text filter now applies in
  search mode too (it was displayed but ignored), invalid filter
  values return a clear error instead of being dropped, and negative
  result-limit values can no longer request the entire archive in one
  response.
- **Knowledge features keep coverage**: FAQ discovery now scans the
  newest end of its window (busy archives previously never saw recent
  questions), and deals auto-extraction survives provider outages — a
  failed run retries on the next sync instead of silently skipping
  messages (cached batches cost nothing to retry).
- **AI robustness**: the one-shot JSON repair path no longer crashes
  when the model returns completely unparseable output.
- **Desktop UI**: the right panel re-evaluates its layout when you
  resize the window; the AI chat no longer mixes up per-turn state
  after its 50-turn history wraps; the Discover view keeps up with
  rapid filter changes; the Research notes editor resets between
  briefs (previously one brief's notes could be saved onto another);
  the Evidence Explorer's "View" jumps focus the referenced record in
  every view.

Full details: `docs/engineering/bug-audit.md` (16 confirmed defects —
a critical sync-engine fix, a cross-record notes-corruption fix, and
fourteen more, each reproduced then fixed with a regression test),
`docs/engineering/performance-report.md` (500k-message benchmark,
before/after), `docs/engineering/release-validation.md` (test results).

## 1.0.1 (2026-11-12)

Desktop-only point release. From this release on, the Windows desktop
app is the only distribution target (decision 0010) — the loopback
server is an embedded detail of the desktop runtime, never a deployment
surface.

- **Native window + tray, hardened**: the app opens in its own WebView2
  window; minimize goes to the tray; the taskbar shows the app's own
  mark (AUMID grouping; `pywin32` is now a declared dependency so the
  Start Menu shortcut never silently skips).
- **Wizard fixed in production builds**: a CSS `@import` placed after
  other rules had silently dropped every per-view stylesheet from
  production bundles — the wizard overlay (and view polish) now
  renders as designed.
- **Right panel flush to the window edge**: the shell grid follows the
  panel's actual width (drag-resize included) instead of a fixed
  360px cell; no `50vw` cap; no blank strip, no ghost column when
  hidden; Ask AI reopens reliably after closing; no dead space above
  the example chips. Verified 1280–1920px, zero console errors
  (41/41 desktop e2e checks).
- **Docs**: deployment runbook archived; README and security docs
  state the desktop-only policy. Dev/test surface unchanged
  (`python app.py`, `--no-window`/`TGQ_NO_WINDOW`).

Upgrading from 1.0.0: run the installer over the old one — data lives
in `%LOCALAPPDATA%\TelegramQuery` and survives upgrade and uninstall by
design.

## 1.0.0 (2026-11-11)

Telegram Query 1.0.0 is the first desktop release: a polished Windows
installer, a full UI/UX overhaul, and a bilingual workspace — with the
same local-first engine underneath.

## Windows installers

- **`TelegramQuery-Setup-x64.exe`** — the standard installer: a small
  bootstrapper with a license prompt that installs the application to
  `Program Files\TelegramQuery`, adds Desktop + Start Menu shortcuts,
  and shows a single "Telegram Query" entry in Add/Remove Programs.
- **`TelegramQuery-x64.msi`** — the same package as a plain MSI for
  silent/scripted installs (`msiexec /i TelegramQuery-x64.msi /qn`).
- No Python, Node, or any other dependency required. The app runs as
  one windowless process; data lives in
  `%LOCALAPPDATA%\TelegramQuery` and **survives uninstall and
  upgrade** by design.
- Verified end-to-end on a clean machine: install → launch → health
  check → single-instance focus → explicit quit → uninstall keeps
  data; port conflicts fall back to a free port (the window still
  opens at the right address); a second launch focuses the first.

## Desktop runtime (packaged builds)

- **A native app window, not a browser tab**: the app opens in its own
  window (Microsoft Edge WebView2, preinstalled on Windows 10/11). A
  missing WebView2 runtime shows an error dialog with the download
  link — there is no browser mode. The UI's localStorage (theme,
  language, panel state) persists in `<data>/webview` across window
  restarts.
- **Minimize to the system tray**: minimizing hides the window from
  the taskbar; left-click the tray icon to restore it, or right-click
  for the menu (Open / Exit). The tray shows the same Paper-Plane
  mark as the executable.
- **Own window icon everywhere**: the taskbar and title bar show the
  app's mark — including a source run of `python desktop.py`. Windows
  requires a Start Menu shortcut carrying the same AppUserModelID for
  the system to group the icon by the app rather than by the Python
  executable; the runtime creates this shortcut automatically.
- Health-gated startup: the window opens only after
  `/api/health/ready` answers — never a blind sleep.
- Loopback-only binding enforced (a non-loopback `HOST` is overridden
  with a warning); busy port 8000 falls back to a free port, recorded
  in `runtime.json` for tooling.
- One instance at a time (named mutex); a second launch focuses the
  running one.
- Explicit Exit in the UI with graceful shutdown (running jobs cancel
  at their checkpoint); no console window; crash visibility via a
  native dialog + rotating log at
  `%LOCALAPPDATA%\TelegramQuery\logs\app.log`.
- Data migration from source installs is copy-based and never
  overwrites: the wizard-era archive beside the app moves into the
  user data dir with a backup, and the Telegram session + settings
  survive.
- Settings now include an explicit **Erase archive** action (typed
  confirmation) — the only way to remove data besides deleting the
  folder yourself.

## UI/UX overhaul

- New visual language: layered research-workspace design system
  (tokens for surfaces, type scale, radii, elevation, motion) with
  refined dark and light themes.
- Self-hosted typography: Inter Variable + Noto Sans Arabic bundle
  with the app (no webfonts, no CDN, works offline).
- All emojis replaced with a consistent Lucide SVG icon system
  (single namespace, one stroke weight, automatic RTL mirroring of
  directional icons).
- **Bilingual UI: English and Arabic** with a language switch — true
  per-component RTL (logical CSS properties everywhere), `<html dir>`
  switching before first paint (no flash), and `dir="auto"` for
  user-authored content so mixed Arabic/Latin text flows correctly.
- Feed performance: memoized message cards with stable handlers —
  store updates (toasts, polling, panel switches) no longer re-render
  hundreds of rows.
- Keyboard access refined (visible focus rings, `/` to focus search),
  empty/loading/error states restyled everywhere.
- Toolbar and panel polish: icon-only ghost buttons for secondary
  actions, redundant View buttons removed (`trend-row` text is already
  clickable), pill-style right-panel segmented tabs, compact AI scope
  chips, denser Discover trending rows, and Discover subtitle reduced
  to a tooltip.

## Engineering

- Packaging pipeline: `scripts/build_windows.py` (frontend →
  PyInstaller onedir → WiX MSI → Burn setup EXE → SHA-256 checksums
  into `dist/release/`), with fixed product-line upgrade GUIDs;
  `scripts/build_frontend.py` enforces web/backend version parity;
  `scripts/test_packaged_app.py` exercises the packaged exe end to
  end (launch, port discovery, health payload, data isolation,
  single instance, graceful quit).
- **Interactive desktop smoke test** (`scripts/e2e_smoke_desktop.py`):
  the real desktop runtime driven through its UI — setup wizard with
  typed + submitted credentials (re-opened from the sidebar footer
  link like a returning user), click-navigation across every view
  and the Ask AI / Jobs / Settings modals, theme & language toggles
  verified across a full window restart, second-launch focus, and
  graceful quit, with a hard zero-console-errors gate. Fully isolated
  (own data dir + `TGQ_ENV_FILE`), so it never touches real data.
- CI now builds and tests the Windows installers on every push.
- Telethon crypto acceleration (`cryptg`) bundled: packaged sync and
  decryption run at native speed.
- Backend tests: 290 passing; the full test gates (ruff, pytest,
  vitest, production build, packaged smoke, desktop UI smoke) run
  green before this release.
- Build fix: a misplaced `@import` block in `app.css` (at the bottom of
  the file, after 458 rules) caused postcss to silently drop *all* view
  stylesheets from production bundles; the setup wizard overlay lost
  `position: fixed` and rendered off-screen, appearing to do nothing.
  Moved the block to the top of the file with a warning comment.

## Upgrade notes

- From source installs: nothing changes for `python app.py` runs —
  the packaged app migrates a legacy archive beside the exe into the
  user data dir on first launch (copy + backup, original untouched).
- From earlier packaged betas: install 1.0.0 over the old version;
  data, settings, and the Telegram session carry over.
- `web/package.json` and `config.__version__` are both 1.0.0 and
  checked in CI.
