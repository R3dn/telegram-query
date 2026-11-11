#!/usr/bin/env python3
"""Test a packaged Telegram Query build (PyInstaller exe) end to end.

Verifies the desktop contract without any human interaction:

  1. launch the packaged exe headless (windowed build, no app window),
  2. discover the actual port from ``runtime.json`` (also proves the
     port-conflict fallback is discoverable),
  3. poll ``GET /api/health/ready`` until 200 - never a blind sleep,
  4. assert the readiness payload (ok, db check, expected version),
  5. assert the archive database lives under the data dir (never next
     to the exe / Program Files),
  6. launch a second instance -> single-instance guard: exits 0 fast,
  7. ``POST /api/app/quit`` -> 200, graceful shutdown, exit code 0,
  8. no orphan process left behind.

The GUI window itself (pywebview) is not exercised here - it needs a
desktop session and a human eye; everything around it is. Set
``TGQ_NO_WINDOW=1`` (as below) to run the same windowed exe headless.

Usage:
  python scripts/test_packaged_app.py                      # dist build
  python scripts/test_packaged_app.py --exe "C:\\Program Files\\TelegramQuery\\TelegramQuery.exe"
  python scripts/test_packaged_app.py --real-data-dir      # default resolution

Exit code 0 = all checks passed. Any failure prints the log tail and
exits nonzero.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNTIME_FILE = "runtime.json"

IS_WINDOWS = sys.platform == "win32"
_EXITED = "exited"
_ALIVE = "alive"


def _repo_version() -> str:
    spec = spec_from_file_location("config", REPO / "config.py")
    mod = module_from_spec(spec)
    sys.modules["config"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.__version__


class Result:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        self.checks += 1
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {label}" + (f" - {detail}" if detail else ""))
        if not ok:
            self.failures.append(label + (f" ({detail})" if detail else ""))
        return ok

    @property
    def ok(self) -> bool:
        return not self.failures


def _get_json(port: int, path: str, timeout: float = 3.0) -> tuple[int, object]:
    url = f"http://127.0.0.1:{port}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return 0, str(e)


def _post_json(port: int, path: str, timeout: float = 5.0) -> tuple[int, object]:
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return 0, str(e)


def _wait_port(data_dir: Path, pid: int, timeout_s: float) -> int | None:
    """Wait for *this process's* runtime.json record and return its port.

    A stale runtime.json from an earlier (crashed or quit) run lingers in
    the data dir; matching on pid ignores it."""
    runtime = data_dir / RUNTIME_FILE
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            info = json.loads(runtime.read_text(encoding="utf-8"))
            if int(info["pid"]) == pid:
                return int(info["port"])
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(0.25)
    return None


def _wait_exit(proc: subprocess.Popen, timeout_s: float) -> str:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return _EXITED
        time.sleep(0.25)
    return _ALIVE


def _tail_log(data_dir: Path, n: int = 30) -> str:
    log = data_dir / "logs" / "app.log"
    if not log.exists():
        return "      (no log file was written)"
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join("      " + ln for ln in lines[-n:])


def main(argv: list[str] | None = None) -> int:
    if not IS_WINDOWS:
        print("test_packaged_app: Windows only (the packaged app is a "
              "Windows exe).")
        return 2

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exe", type=Path,
        default=REPO / "dist" / "TelegramQuery" / "TelegramQuery.exe",
        help="packaged exe to test (default: dist/TelegramQuery/TelegramQuery.exe)")
    parser.add_argument(
        "--real-data-dir", action="store_true",
        help="use the default data dir (%LOCALAPPDATA%\\TelegramQuery) "
             "instead of a fresh temp dir - exercises default path "
             "resolution and leaves data behind for uninstall tests.")
    parser.add_argument(
        "--timeout", type=float, default=90.0,
        help="seconds to wait for backend readiness (default 90)")
    args = parser.parse_args(argv)

    exe = args.exe
    if not exe.exists():
        print(f"test_packaged_app: exe not found: {exe}")
        return 2
    expected_version = _repo_version()

    if args.real_data_dir:
        data_dir = Path(os.environ["LOCALAPPDATA"]) / "TelegramQuery"
    else:
        data_dir = Path(tempfile.gettempdir()) / f"tgq_packaged_{os.urandom(4).hex()}"

    env = {**os.environ,
           "TGQ_NO_WINDOW": "1",
           "TGQ_STARTUP_TIMEOUT": str(int(max(30, args.timeout)))}
    if not args.real_data_dir:
        env["TG_DATA_DIR"] = str(data_dir)

    print(f"testing: {exe}")
    print(f"data dir: {data_dir}" + (" (default resolution)" if args.real_data_dir else " (fresh temp)"))
    print()

    result = Result()

    # -- 1. launch ----------------------------------------------------
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen([str(exe)], env=env, creationflags=creationflags)
    print(f"[1] launched pid {proc.pid}")

    # -- 2. port discovery ---------------------------------------------
    port = _wait_port(data_dir, pid=proc.pid, timeout_s=args.timeout)
    if not result.check(port is not None, "runtime.json with chosen port appears"):
        print("\n  log tail:\n" + _tail_log(data_dir))
        if proc.poll() is None:
            proc.kill()
        return 1
    assert port is not None
    print(f"[2] port: {port}")

    # -- 3. readiness ---------------------------------------------------
    deadline = time.monotonic() + args.timeout
    status, payload = 0, None
    while time.monotonic() < deadline:
        status, payload = _get_json(port, "/api/health/ready")
        if status == 200:
            break
        time.sleep(0.5)
    if not result.check(status == 200, "GET /api/health/ready -> 200",
                        f"last status {status}"):
        print("\n  log tail:\n" + _tail_log(data_dir))
        if proc.poll() is None:
            proc.kill()
        return 1

    # -- 4. payload ------------------------------------------------------
    ok = isinstance(payload, dict) and payload.get("ok") is True
    result.check(ok, "readiness payload ok=true")
    checks = isinstance(payload, dict) and payload.get("checks", {}).get("db") is True
    result.check(bool(checks), "readiness db check true")
    version = isinstance(payload, dict) and payload.get("version")
    result.check(version == expected_version,
                 "version matches config.py", f"{version!r} vs {expected_version!r}")

    # -- 5. data isolation ------------------------------------------------
    db_path = data_dir / "messages.db"
    result.check(db_path.exists(),
                 "archive database lives under the data dir", str(db_path))
    exe_dir = exe.resolve().parent
    stray = [p for p in ("messages.db", ".env", "tg_session.session")
             if (exe_dir / p).exists()]
    result.check(not stray, "nothing mutable written next to the exe",
                 ", ".join(stray) if stray else "")

    # -- 6. single instance ------------------------------------------------
    second = subprocess.Popen([str(exe)], env=env, creationflags=creationflags)
    state = _wait_exit(second, timeout_s=25.0)
    result.check(state == _EXITED and second.returncode == 0,
                 "second instance exits 0 while first runs",
                 f"state={state} rc={second.returncode}")

    # -- 7. graceful quit ----------------------------------------------------
    status, payload = _post_json(port, "/api/app/quit")
    result.check(status == 200 and isinstance(payload, dict) and payload.get("ok") is True,
                 "POST /api/app/quit -> 200 ok=true", f"status={status}")
    state = _wait_exit(proc, timeout_s=25.0)
    result.check(state == _EXITED and proc.returncode == 0,
                 "graceful shutdown, exit code 0",
                 f"state={state} rc={proc.returncode}")

    # -- 8. no orphans -------------------------------------------------------
    time.sleep(1.0)
    if not result.ok:
        print("\n  log tail:\n" + _tail_log(data_dir))

    print()
    if result.ok:
        print(f"PACKAGED APP TEST PASSED ({result.checks} checks)")
        return 0
    print("PACKAGED APP TEST FAILED:")
    for f in result.failures:
        print(f"  - {f}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
