# Release notes — 1.0.0

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
  data; port conflicts fall back to a free port (the browser still
  opens at the right address); a second launch focuses the first.

## Desktop runtime (packaged builds)

- Health-gated startup: the browser opens only after
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

## Engineering

- Packaging pipeline: `scripts/build_windows.py` (frontend →
  PyInstaller onedir → WiX MSI → Burn setup EXE → SHA-256 checksums
  into `dist/release/`), with fixed product-line upgrade GUIDs;
  `scripts/build_frontend.py` enforces web/backend version parity;
  `scripts/test_packaged_app.py` exercises the packaged exe end to
  end (launch, port discovery, health payload, data isolation,
  single instance, graceful quit).
- CI now builds and tests the Windows installers on every push.
- Telethon crypto acceleration (`cryptg`) bundled: packaged sync and
  decryption run at native speed.
- Backend tests: 274 passing; the full test gates (ruff, pytest,
  vitest, production build, packaged smoke) run green before this
  release.

## Upgrade notes

- From source installs: nothing changes for `python app.py` runs —
  the packaged app migrates a legacy archive beside the exe into the
  user data dir on first launch (copy + backup, original untouched).
- From earlier packaged betas: install 1.0.0 over the old version;
  data, settings, and the Telegram session carry over.
- `web/package.json` and `config.__version__` are both 1.0.0 and
  checked in CI.
