#!/usr/bin/env python3
"""End-to-end Windows packaging pipeline.

Produces:
  dist/release/TelegramQuery-x64.msi
  dist/release/TelegramQuery-Setup-x64.exe

Steps:
  1. validate environment (npm, pyinstaller, WiX tools)
  2. build React frontend
  3. PyInstaller onedir build
  4. heat harvest -> Files.wxs
  5. candle + light -> MSI
  6. candle + light -> Burn bootstrapper EXE
  7. checksums + release manifest
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WIX_DIR = REPO / "packaging" / "windows" / "tools" / "wix314"
ASSETS = REPO / "packaging" / "windows" / "assets"
WIX_TEMPLATES = REPO / "packaging" / "windows" / "wix"
DIST = REPO / "dist"
RELEASE = DIST / "release"
FROZEN = DIST / "TelegramQuery"

# Fixed product-line GUIDs (never change between versions)
_UPGRADE_GUID = "6c8e2f4a-3b5d-4a7e-8f1c-9d2e5b6a7c8d"
_BUNDLE_UPGRADE_GUID = "7d9f3e5b-4c6a-5b8e-9f2d-0e1f3a4b5c6d"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print("> ", end="")
    print(*cmd)
    subprocess.run(cmd, cwd=cwd or REPO, check=True)


def version() -> str:
    """Return 4-part version string for WiX (e.g. 1.0.0.0)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("config", REPO / "config.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["config"] = mod
    spec.loader.exec_module(mod)
    v = mod.__version__
    parts = v.split(".")
    while len(parts) < 4:
        parts.append("0")
    return ".".join(parts[:4])


def ensure_wix() -> None:
    if (WIX_DIR / "candle.exe").exists():
        return
    WIX_DIR.mkdir(parents=True, exist_ok=True)
    url = (
        "https://github.com/wixtoolset/wix3/releases/download/"
        "wix3141rtm/wix314-binaries.zip"
    )
    zip_path = Path(tempfile.gettempdir()) / "wix314-binaries.zip"
    if not zip_path.exists():
        print("downloading WiX 3.14 binaries ...")
        urllib.request.urlretrieve(url, zip_path)
    shutil.unpack_archive(zip_path, WIX_DIR)
    print("WiX ready at", WIX_DIR)


def build_frontend() -> None:
    """Delegate to scripts/build_frontend.py (also enforces the
    web/package.json <-> config.py version match)."""
    print("building frontend ...")
    _run([sys.executable, str(REPO / "scripts" / "build_frontend.py")])
    print("frontend build ok")


def build_pyinstaller() -> None:
    print("building PyInstaller onedir ...")
    spec = REPO / "packaging" / "windows" / "pyinstaller" / "TelegramQuery.spec"
    _run(
        ["python", "-m", "PyInstaller", str(spec), "--clean", "--noconfirm"],
        cwd=REPO,
    )
    if not (FROZEN / "TelegramQuery.exe").exists():
        raise RuntimeError("PyInstaller did not produce TelegramQuery.exe")
    print("PyInstaller ok")


def build_msi(ver: str) -> Path:
    print("building MSI ...")
    tmp = DIST / "wix"
    tmp.mkdir(parents=True, exist_ok=True)
    heat = WIX_DIR / "heat.exe"
    files_wxs = tmp / "Files.wxs"
    _run(
        [
            str(heat),
            "dir",
            str(FROZEN),
            "-cg",
            "TelegramQueryFiles",
            "-gg",
            "-sfrag",
            "-sreg",
            "-srd",
            "-ke",
            "-scompl",
            "-dr",
            "INSTALLDIR",
            "-out",
            str(files_wxs),
        ]
    )

    # substitute tokens
    template = (WIX_TEMPLATES / "TelegramQuery.wxs").read_text(encoding="utf-8")
    msi_wxs = tmp / "TelegramQuery.wxs"
    msi_wxs.write_text(
        template
        .replace("@@VERSION@@", ver)
        .replace("@@UPGRADE_GUID@@", _UPGRADE_GUID)
        .replace("@@ICON@@", str(ASSETS / "app.ico")),
        encoding="utf-8",
    )

    obj = tmp / "obj"
    obj.mkdir(exist_ok=True)
    candle = WIX_DIR / "candle.exe"
    light = WIX_DIR / "light.exe"
    _run(
        [
            str(candle),
            "-arch",
            "x64",
            str(msi_wxs),
            str(files_wxs),
            "-o",
            str(obj) + os.sep,
        ]
    )
    msi_out = RELEASE / "TelegramQuery-x64.msi"
    _run(
        [
            str(light),
            str(obj / "TelegramQuery.wixobj"),
            str(obj / "Files.wixobj"),
            "-b",
            str(FROZEN),
            "-sice:ICE57",
            "-o",
            str(msi_out),
        ]
    )
    # light writes linker debug symbols next to the output; not a
    # release artifact - drop them from the release folder.
    msi_out.with_suffix(".wixpdb").unlink(missing_ok=True)
    print("MSI ready:", msi_out)
    return msi_out


def build_bundle(ver: str, msi: Path) -> Path:
    print("building Burn bootstrapper ...")
    tmp = DIST / "wix"
    template = (WIX_TEMPLATES / "Bundle.wxs").read_text(encoding="utf-8")
    bundle_wxs = tmp / "Bundle.wxs"
    bundle_wxs.write_text(
        template
        .replace("@@VERSION@@", ver)
        .replace("@@BUNDLE_UPGRADE_GUID@@", _BUNDLE_UPGRADE_GUID)
        .replace("@@ICON@@", str(ASSETS / "app.ico"))
        .replace("@@LICENSE@@", str(ASSETS / "license.rtf"))
        .replace("@@MSI@@", str(msi)),
        encoding="utf-8",
    )
    candle = WIX_DIR / "candle.exe"
    light = WIX_DIR / "light.exe"
    obj = tmp / "obj"
    _run(
        [
            str(candle),
            "-arch",
            "x64",
            str(bundle_wxs),
            "-o",
            str(obj) + os.sep,
            "-ext",
            "WixBalExtension",
        ]
    )
    exe_out = RELEASE / "TelegramQuery-Setup-x64.exe"
    _run(
        [
            str(light),
            str(obj / "Bundle.wixobj"),
            "-o",
            str(exe_out),
            "-ext",
            "WixBalExtension",
        ]
    )
    exe_out.with_suffix(".wixpdb").unlink(missing_ok=True)
    print("Bootstrapper ready:", exe_out)
    return exe_out


def checksums() -> None:
    print("writing checksums ...")
    manifest: dict[str, str] = {}
    for f in sorted(RELEASE.iterdir()):
        if f.is_file() and f.name != "checksums.json":
            sha = hashlib.sha256(f.read_bytes()).hexdigest()
            manifest[f.name] = sha
            print(f"  {f.name}  {sha}")
    (RELEASE / "checksums.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    skip_frontend = "--skip-frontend" in argv
    skip_pyinstaller = "--skip-pyinstaller" in argv

    ensure_wix()
    ver = version()
    RELEASE.mkdir(parents=True, exist_ok=True)

    if not skip_frontend:
        build_frontend()
    if not skip_pyinstaller:
        build_pyinstaller()

    msi = build_msi(ver)
    build_bundle(ver, msi)
    checksums()

    print("\nrelease artifacts:")
    for f in sorted(RELEASE.iterdir()):
        if f.is_file():
            print(f"  {f.name:40s}  {f.stat().st_size:>12,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
