#!/usr/bin/env python3
"""Build the React frontend into web/dist (the directory the packaged
app serves).

Steps:
  1. require node + npm (honest error, not a stack trace)
  2. verify web/package.json version matches config.__version__ -
     the shipped UI and the backend must never disagree
  3. npm ci (clean, reproducible install from package-lock.json)
  4. npm run build (tsc --noEmit + vite build - production bundle)
  5. verify the bundle exists and report its size

Exit code 0 on success, nonzero with a clear message otherwise.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "web"
DIST = WEB / "dist"


def _run(cmd: list[str]) -> None:
    print("> ", end="")
    print(*cmd)
    subprocess.run(cmd, cwd=WEB, check=True)


def _repo_version() -> str:
    spec = spec_from_file_location("config", REPO / "config.py")
    mod = module_from_spec(spec)
    sys.modules["config"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.__version__


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    npm = shutil.which("npm")
    if npm is None:
        print("build_frontend: npm not found - install Node.js LTS "
              "(https://nodejs.org) and make sure npm is on PATH.")
        return 2
    # shutil.which resolves to npm.cmd on Windows (subprocess cannot
    # resolve extension-less .cmd names via PATH on its own).

    web_version = json.loads((WEB / "package.json").read_text(
        encoding="utf-8"))["version"]
    backend_version = _repo_version()
    if web_version != backend_version:
        print(f"build_frontend: version mismatch - web/package.json "
              f"says {web_version} but config.py says {backend_version}. "
              "They must match for a release.")
        return 2
    print(f"version {backend_version} (web == backend)")

    _run([npm, "ci"])
    _run([npm, "run", "build"])

    index = DIST / "index.html"
    if not index.exists():
        print("build_frontend: build finished but web/dist/index.html "
              "is missing - vite output layout changed?")
        return 1
    total = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    print(f"web/dist ready: {index}")
    print(f"  {sum(1 for _ in DIST.rglob('*') if _.is_file())} files, "
          f"{total / 1024:.0f} KiB total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
