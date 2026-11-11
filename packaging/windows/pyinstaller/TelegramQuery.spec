# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec for Telegram Query.

Produces a windowed, console-free directory (TelegramQuery/) containing
TelegramQuery.exe and all support files. The built React frontend lives at
web/dist inside the support dir, matching the frozen path resolution in
config.py.
"""

import sys
from pathlib import Path

# SPECPATH is the directory containing this file.
repo = Path(SPECPATH).resolve().parents[2]  # packaging/windows/pyinstaller -> repo root

block_cipher = None

# Every top-level module that might escape static analysis (dynamic imports
# inside functions, lifespan hooks, or plain runtime imports).
_hidden = [
    # root modules (dynamic or plain-import)
    "app", "migration", "auth", "config", "db", "deals", "decisions",
    "entities", "jobs", "research", "scheduler", "sync", "watchlists",
    "digests", "discover", "ai", "ai_tasks", "faq",
    # api routers
    "api", "api.ai", "api.archive", "api.auth", "api.bookmarks",
    "api.data", "api.deals", "api.decisions", "api.digests",
    "api.discover", "api.evidence", "api.exports", "api.faqs",
    "api.general", "api.groups", "api.jobs", "api.monitor",
    "api.research", "api.saved", "api.scheduler", "api.setup",
    # networking / AI / Telegram
    "openai", "httpx",
    "telethon", "telethon.errors", "telethon.sessions.sqlite",
    # ASGI / web stack (uvicorn lazily loads protocol implementations)
    "uvicorn", "uvicorn.logging", "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
    "fastapi", "pydantic",
    # env loader
    "dotenv",
    # Telethon crypto accelerator (optional at runtime, bundled here so
    # packaged sync/decryption runs at native speed instead of Telethon's
    # slow pure-Python fallback)
    "cryptg",
]

a = Analysis(
    [str(repo / "desktop.py")],
    pathex=[str(repo)],
    binaries=[],
    datas=[(str(repo / "web" / "dist"), "web/dist")],
    hiddenimports=_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PIL", "matplotlib", "numpy", "pandas", "pytest", "tkinter"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TelegramQuery",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(repo / "packaging" / "windows" / "assets" / "app.ico")],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TelegramQuery",
)
