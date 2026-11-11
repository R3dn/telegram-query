# Windows packaging

Builds the two release artifacts from one MSI definition:

```
dist/release/
├─ TelegramQuery-x64.msi         per-machine MSI (MajorUpgrade-capable)
├─ TelegramQuery-Setup-x64.exe   Burn bootstrapper chaining that MSI
└─ checksums.json                SHA-256 for every artifact
```

## Build

```bash
pip install -r requirements.txt -r packaging/windows/requirements-packaging.txt
python scripts/build_windows.py
```

Prerequisites: Python 3.10+, Node 20+ on PATH (frontend build), and
network access on the first run only (the script downloads the portable
WiX 3.14 toolset into `packaging/windows/tools/wix314/`, gitignored,
and reuses it afterward). `--skip-frontend` / `--skip-pyinstaller` let
you re-run just the installer stages during template work.

CI runs the same command on `windows-2022` (`.github/workflows/ci.yml`,
job `packaging`) and uploads `dist/release/` as artifacts.

## Layout

```
packaging/windows/
├─ pyinstaller/TelegramQuery.spec   onedir, windowed (no console), icon,
│                                    web/dist + hidden imports + cryptg
├─ wix/TelegramQuery.wxs            MSI definition (tokens: @@VERSION@@,
│                                    @@UPGRADE_GUID@@, @@ICON@@)
├─ wix/Bundle.wxs                   Burn bootstrapper (RtfLicense UI,
│                                    chains the MSI, passes TGQBUNDLED=1)
├─ assets/                          app.ico (8-frame), license.rtf, …
├─ scripts/make_icon.py             icon generator (run when changing art)
├─ requirements-packaging.txt       PyInstaller + cryptg (build-time only)
└─ tools/wix314/                    downloaded WiX toolset (gitignored)
```

`scripts/test_packaged_app.py` exercises the built exe end to end
(launch, health, data isolation, single instance, graceful quit) and
is the packaging CI gate. Install/uninstall behavior on a clean
machine is validated manually per release (see the release checklist
in the wiki).

## Rules learned the hard way

- **The upgrade GUIDs never change.** `UpgradeCode` (MSI) and the
  bundle `UpgradeCode` are product identity across versions; they are
  defined in `scripts/build_windows.py` and referenced by the WiX
  templates. Regenerating them orphans every installed copy.
- **Same-version rebuilds must still upgrade**: `MajorUpgrade` needs
  `AllowSameVersionUpgrades="yes"` — otherwise installing a rebuilt
  1.0.0.0 MSI over an installed 1.0.0.0 registers a SECOND product
  side-by-side and leaves stale hashed assets in Program Files
  (RC cycles and packaging fixes hit this; real version bumps don't).
- **WiX `Version` needs 4 parts** (`1.0.0.0`); `scripts/build_windows.py`
  derives it from `config.__version__`.
- **Per-machine MSIs need HKMU keypaths** for the shortcut components
  (HKCU keypaths are per-user data in a per-machine package → ICE57).
  ICE57 is suppressed with `-sice:ICE57`, the accepted stance for
  per-machine packages with per-user-visible shortcuts.
- **One ARP entry**: Burn itself passes `ARPSYSTEMCOMPONENT=1` to
  chained MSIs, and the MSI additionally hides its own entry when the
  property `TGQBUNDLED=1` is set (only the bundle sets it) — so the
  Setup EXE shows exactly one "Telegram Query" while a direct MSI
  install still shows its own entry.
- **`heat` needs `-dr INSTALLDIR`** or files land under TARGETDIR;
  `light` needs `-b <frozen dir>` to resolve harvested `SourceDir`
  paths; the bundle link needs `-ext WixBalExtension` on both candle
  and light.
- **PyInstaller entry-point quirk**: the entry script runs as
  `__main__`; any module importing `desktop` by name gets a duplicate
  module with its own globals. `desktop.py` aliases
  `sys.modules["desktop"] = sys.modules["__main__"]` at startup —
  without it the packaged app exits instantly or `/api/app/quit`
  can't reach the runtime.
- **The frontend version must match the backend**:
  `scripts/build_frontend.py` fails the build when
  `web/package.json` and `config.__version__` disagree.
- Never bundle real data: the spec picks up `web/dist` and code only.
  The repo `data/` directory, `.env`, and session files are never
  packaged (and `.gitignore` keeps them out of source control).
