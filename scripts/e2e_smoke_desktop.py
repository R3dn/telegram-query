"""Interactive E2E smoke test for the Telegram Query desktop app.

Boots the real desktop runtime (``desktop.py``) in a fully isolated
environment (own data dir, own ``.env`` via ``TGQ_ENV_FILE`` - the real
``.env`` is never read or written) and drives the same React UI the
native window renders, through Playwright:

  [1] boot & health        - desktop mode, unauthenticated, unconfigured
  [2] setup wizard        - click-through, type Telegram credentials,
                            submit, credential persistence to the
                            isolated .env, dismiss
  [3] navigation          - Discover, Entities, Browse & search (typed
                            query), Bookmarks via sidebar clicks + Ask
                            AI tab + Jobs modal + Settings modal
  [4] theme & language    - real sidebar toggles; localStorage and
                            <html> state both flip
  [5] window restart      - graceful quit, relaunch, verify theme and
                            language persist and the submitted
                            credentials survived the restart
  [6] second launch       - discovers the running instance, exits fast
  [7] graceful quit       - POST /api/app/quit, process exit code 0
  [8] console hygiene     - zero console errors / page errors across
                            every interaction (both sessions)

Playwright approximates the WebView2 window: same HTTP endpoint, same
production React build, same localStorage semantics. A persistent
browser profile under the temp data dir mirrors the app's own
``<data>/webview`` WebView2 profile, so "window restart" is faithful.
The real Telegram login step cannot complete without a real account,
so the wizard is exercised with syntactically valid fake credentials
(the backend validates and persists them exactly like real ones).

Requires (dev-only):
    pip install playwright && python -m playwright install chromium

Usage:
    python scripts/e2e_smoke_desktop.py
    python scripts/e2e_smoke_desktop.py --headed     # watch it run

Exit codes: 0 = all passed, 1 = any failure (details printed).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402

PASS: list[str] = []
FAIL: list[str] = []

# Everything the child process must NOT inherit from this shell: the
# test owns the whole environment. Real credentials in the parent env
# or the repo .env must never leak into the run.
_ISOLATED_KEYS = (
    "TG_API_ID", "TG_API_HASH", "TELEGRAM_API_ID", "TELEGRAM_API_HASH",
    "AI_API_KEY", "AI_BASE_URL", "AI_MODEL", "AI_MODEL_EXTRACT",
    "AI_MODEL_SYNTH", "AI_MODEL_EMBED", "TGQ_GROUPS_HINT",
    "HOST", "PORT", "TGQ_ENV_FILE",
)

FAKE_API_ID = "12345678"
FAKE_API_HASH = "e2e" + "a" * 29            # 32 alphanumerics, like a real one

CONSOLE: list[tuple[str, str, str]] = []    # (phase, type, text)
PAGE_ERRORS: list[str] = []


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def check(name: str, cond: bool, detail: str = "") -> bool:
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}" + (f"  [{detail}]" if detail else ""))
    return cond


def _tail(path: Path, lines: int = 40) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return f"<no log at {path}>"
    return "\n".join(text.splitlines()[-lines:])


def wait_until(fn, timeout_s: float = 5.0, interval: float = 0.2):
    """Poll fn() until truthy or the deadline passes."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        result = fn()
        if result:
            return result
        time.sleep(interval)
    return None


# ---------------------------------------------------------------------------
# Desktop runtime process management
# ---------------------------------------------------------------------------

def kill_stale_packaged_app() -> None:
    """A stale packaged TelegramQuery.exe holds the single-instance
    mutex and would break the test. Only the app's own exe is targeted -
    never arbitrary python processes."""
    r = subprocess.run(
        ["taskkill", "/F", "/IM", "TelegramQuery.exe"],
        capture_output=True, text=True)
    if r.returncode == 0:
        print("note: closed a stale packaged Telegram Query instance")


def start_desktop(data_dir: Path) -> tuple[subprocess.Popen, int, Path]:
    """Boot desktop.py isolated; return (proc, port, stdout-log path)."""
    env = {k: v for k, v in os.environ.items() if k not in _ISOLATED_KEYS}
    env.update({
        "TG_DATA_DIR": str(data_dir),
        "TGQ_ENV_FILE": str(data_dir / ".env"),
        "TGQ_STARTUP_TIMEOUT": "90",
        "PYTHONUNBUFFERED": "1",
    })

    stdout_log = data_dir / "desktop-stdout.log"
    out_file = open(stdout_log, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [sys.executable, "-u", str(ROOT / "desktop.py")],
        env=env, stdout=out_file, stderr=subprocess.STDOUT,
        text=True, cwd=ROOT)

    runtime_file = data_dir / "runtime.json"
    port = None
    for _ in range(90):
        time.sleep(1)
        if proc.poll() is not None:                    # exited early
            text = _tail(stdout_log)
            if "another instance" in text:
                raise SystemExit(
                    "Another Telegram Query instance holds the "
                    "single-instance mutex (a source run of desktop.py "
                    "or app.py). Close it and rerun.\n--- process log ---"
                    f"\n{text}")
            raise SystemExit(
                "desktop.py exited during startup.\n"
                f"--- process log ---\n{text}")
        if runtime_file.exists():
            try:
                port = int(json.loads(
                    runtime_file.read_text(encoding="utf-8"))["port"])
                if port:
                    break
            except (ValueError, KeyError, OSError):
                pass

    if port is None:
        proc.kill()
        raise SystemExit(
            "desktop.py did not write runtime.json.\n"
            f"--- process log ---\n{_tail(stdout_log)}")

    ok = wait_until(lambda: _ready(port), timeout_s=30, interval=0.5)
    if not ok:
        proc.kill()
        raise SystemExit(
            "backend never became healthy.\n"
            f"--- process log ---\n{_tail(stdout_log)}")
    return proc, port, stdout_log


def _ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/health/ready",
                timeout=2) as resp:
            return json.loads(resp.read().decode()).get("ok") is True
    except Exception:
        return False


def _post_json(port: int, path: str) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=b"{}", method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw}


def stop_desktop(proc: subprocess.Popen, port: int,
                 data_dir: Path, timeout_s: int = 40) -> int:
    """POST the in-app quit and wait for a clean exit code."""
    _post_json(port, "/api/app/quit")
    try:
        exit_code = proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        print("  ....  quit timed out - killing; logs follow")
        print(f"--- process log ---\n{_tail(data_dir / 'desktop-stdout.log')}")
        print(f"--- app.log ---\n{_tail(data_dir / 'logs' / 'app.log')}")
        proc.kill()
        proc.wait()
        exit_code = 1
    return exit_code or 0


# ---------------------------------------------------------------------------
# UI plumbing
# ---------------------------------------------------------------------------

def attach(page, phase: str) -> None:
    """Collect console output + uncaught page errors for the whole run."""
    page.on("console",
            lambda m: CONSOLE.append((phase, m.type, m.text)))
    page.on("pageerror", lambda e: PAGE_ERRORS.append(f"[{phase}] {e}"))


def open_ui(p, profile_dir: Path, headless: bool, phase: str):
    """A persistent browser context mirrors the app's WebView2 profile:
    localStorage survives close + relaunch exactly like a window
    restart."""
    ctx = p.chromium.launch_persistent_context(
        str(profile_dir), headless=headless,
        viewport={"width": 1400, "height": 900})
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    attach(page, phase)
    return ctx, page


def goto_app(page, base: str) -> None:
    """Load the app; an unauthenticated session auto-opens the wizard,
    so dismiss it the way a user would (its X button)."""
    page.goto(base)
    page.wait_for_selector(".app", timeout=20000)
    try:
        page.wait_for_selector(".wizard", timeout=5000)
        page.click(".wizard-head .btn")
        page.wait_for_selector(".wizard", state="detached", timeout=8000)
    except Exception:
        pass                                   # wizard already closed


# ---------------------------------------------------------------------------
# [1] boot & health
# ---------------------------------------------------------------------------

def test_health(port: int) -> None:
    print("\n[1] boot & health (isolated data dir + isolated .env)")
    with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/health", timeout=5) as r:
        body = json.loads(r.read().decode())
    check("health 200 + version",
          body.get("version") == config.__version__,
          f"got={body.get('version')}")

    with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/app/state", timeout=5) as r:
        state = json.loads(r.read().decode())
    check("desktop mode", state.get("desktop_mode") is True)
    check("starts unauthenticated", state.get("authenticated") is False)
    check("starts unconfigured",
          state.get("telegram_configured") is False,
          f"got={state.get('telegram_configured')}")


# ---------------------------------------------------------------------------
# [2] setup wizard
# ---------------------------------------------------------------------------

def test_wizard(page, base: str, env_file: Path) -> None:
    print("\n[2] setup wizard: click-through, type + submit credentials")
    page.goto(base)
    page.wait_for_selector(".app", timeout=20000)
    page.wait_for_selector(".wizard", timeout=8000)
    check("wizard opens on a fresh profile",
          page.locator(".wizard").count() > 0)

    page.wait_for_selector("#tg-api-id", timeout=8000)
    page.fill("#tg-api-id", FAKE_API_ID)
    page.fill("#tg-api-hash", FAKE_API_HASH)
    check("credentials typed",
          page.input_value("#tg-api-id") == FAKE_API_ID
          and page.input_value("#tg-api-hash") == FAKE_API_HASH)

    # Save & Continue: the backend validates, writes the isolated .env,
    # and the wizard advances to the Telegram login step.
    page.click(".wizard .wizard-actions .btn.primary")
    page.wait_for_selector(
        "input[placeholder='+966501234567']", timeout=10000)
    check("wizard advanced to the Telegram login step", True)
    check("submit persisted the credentials",
          env_file.exists() and f"TG_API_ID={FAKE_API_ID}"
          in env_file.read_text(encoding="utf-8"))

    # Dismiss via the wizard's X, then re-open from the sidebar footer -
    # the exact path a user takes once the wizard has already been closed.
    page.click(".wizard-head .btn")
    page.wait_for_selector(".wizard", state="detached", timeout=8000)
    check("wizard dismissed", page.locator(".wizard").count() == 0)

    page.locator(".side-bottom button.link",
                 has_text="Setup wizard").first.click()
    page.wait_for_selector(".wizard", timeout=8000)
    check("sidebar link re-opens the wizard",
          page.locator(".wizard").count() > 0)
    check("re-opened wizard renders a step body",
          page.locator(".wizard-body").inner_text().strip() != "")
    page.click(".wizard-head .btn")
    page.wait_for_selector(".wizard", state="detached", timeout=8000)


# ---------------------------------------------------------------------------
# [3] navigation by clicking
# ---------------------------------------------------------------------------

def test_navigation(page, base: str) -> None:
    print("\n[3] navigation: Discover -> Entities -> Browse & search "
          "-> Bookmarks, Ask AI, Jobs, Settings")
    goto_app(page, base)
    page.wait_for_selector(".sidebar", timeout=8000)

    # (label, active-nav assertion, view landmark)
    views = [
        ("Discover", ".center .feed-col"),
        ("Entities", ".center .feed-col"),
        ("Browse & search", ".searchbox"),
        ("Bookmarks", ".center .feed-col"),
    ]
    def _nav_active(label: str) -> bool:
        """Poll until the sidebar marks *label* as the active view."""
        return bool(wait_until(
            lambda: page.locator(".nav-item.on",
                                 has_text=label).count() > 0, 5))

    for label, landmark in views:
        page.locator(".nav-item", has_text=label).first.click()
        check(f"nav click: {label} becomes active", _nav_active(label))
        check(f"view renders: {label}",
              page.locator(landmark).count() > 0,
              f"missing {landmark}")

    # Type a search query and submit it (real form interaction).
    page.locator(".nav-item", has_text="Browse & search").first.click()
    wait_until(lambda: page.locator(".searchbox .input").count() > 0, 5)
    page.fill(".searchbox .input", "offers")
    page.keyboard.press("Enter")
    wait_until(lambda: page.locator(".center .feed-col").count() > 0, 5)
    check("search submitted from the browse view",
          page.locator(".center .feed-col").count() > 0)

    # Ask AI opens the right panel's AI tab.
    page.locator(".nav-item", has_text="Ask AI").first.click()
    active = wait_until(
        lambda: page.locator(".right-tabs .tab.on").count() > 0, 5)
    check("Ask AI opens the AI panel", bool(active))

    # Jobs opens a modal; the header X closes it.
    page.locator(".nav-item", has_text="Jobs").first.click()
    page.wait_for_selector(".modal-overlay", timeout=8000)
    check("Jobs modal opens", page.locator(".modal").count() > 0)
    page.click(".modal-head .btn")
    page.wait_for_selector(".modal-overlay", state="detached",
                           timeout=8000)
    check("modal closes via its X", page.locator(".modal").count() == 0)

    # Settings modal from the sidebar footer.
    page.locator(".side-bottom button.link",
                 has_text="Settings").first.click()
    page.wait_for_selector(".modal-overlay", timeout=8000)
    check("Settings modal opens", page.locator(".modal").count() > 0)
    page.click(".modal-head .btn")
    page.wait_for_selector(".modal-overlay", state="detached",
                           timeout=8000)
    check("Settings closes via its X",
          page.locator(".modal").count() == 0)


# ---------------------------------------------------------------------------
# [4] theme & language (real UI toggles)
# ---------------------------------------------------------------------------

def test_theme_language(page, base: str) -> None:
    print("\n[4] theme & language toggles")
    goto_app(page, base)

    # Sidebar footer: theme toggle (title flips with the current theme).
    page.click('button[title="Light theme"]')       # dark -> light
    check("light theme applied to <html>",
          bool(wait_until(lambda: page.evaluate(
              "document.documentElement.classList.contains('light')"), 5)))
    check("theme stored in localStorage",
          page.evaluate("localStorage.getItem('tgq-theme')") == "light")

    # Language toggle: English -> Arabic (hardcoded titles in the UI).
    page.click('button[title="العربية"]')
    check("Arabic applied to <html lang>",
          bool(wait_until(lambda: page.evaluate(
              "document.documentElement.lang") == "ar", 5)))
    check("RTL direction applied",
          page.evaluate("document.documentElement.dir") == "rtl")
    check("language stored in localStorage",
          page.evaluate("localStorage.getItem('tgq-lang')") == "ar")


# ---------------------------------------------------------------------------
# [5] window restart
# ---------------------------------------------------------------------------

def test_restart(p, data_dir: Path, profile_dir: Path, headless: bool,
                 proc: subprocess.Popen, port: int
                 ) -> tuple[subprocess.Popen, int, object, object]:
    """Quit, relaunch the app, reopen the window profile - theme,
    language, and the submitted credentials must all survive."""
    print("\n[5] window restart: theme/language/credentials persist")
    exit_code = stop_desktop(proc, port, data_dir)
    check("graceful quit (window close path), exit 0", exit_code == 0,
          f"got={exit_code}")

    proc2, port2, _ = start_desktop(data_dir)
    base2 = f"http://127.0.0.1:{port2}"
    print(f"  ....  relaunched on {base2}")

    with urllib.request.urlopen(
            f"http://127.0.0.1:{port2}/api/app/state", timeout=5) as r:
        state = json.loads(r.read().decode())
    check("submitted credentials survived the restart",
          state.get("telegram_configured") is True)

    # Same browser profile dir = same window storage as the real app.
    ctx2, page2 = open_ui(p, profile_dir, headless, "after-restart")
    page2.goto(base2)
    page2.wait_for_selector(".app", timeout=20000)

    check("theme persisted across restart",
          page2.evaluate("localStorage.getItem('tgq-theme')") == "light"
          and bool(wait_until(lambda: page2.evaluate(
              "document.documentElement.classList.contains('light')"), 5)))
    check("language persisted across restart",
          page2.evaluate("localStorage.getItem('tgq-lang')") == "ar"
          and page2.evaluate("document.documentElement.lang") == "ar"
          and page2.evaluate("document.documentElement.dir") == "rtl")

    # The restarted window is interactive: dismiss the auto-opened
    # wizard and click the first nav item.
    page2.wait_for_selector(".wizard", timeout=8000)
    page2.click(".wizard-head .btn")
    page2.wait_for_selector(".wizard", state="detached", timeout=8000)
    check("restarted window is interactive",
          page2.locator(".wizard").count() == 0)
    return proc2, port2, ctx2, page2


# ---------------------------------------------------------------------------
# [6] second launch, [7] final quit
# ---------------------------------------------------------------------------

def test_second_launch(data_dir: Path) -> None:
    print("\n[6] second launch focuses the running instance")
    env = {k: v for k, v in os.environ.items() if k not in _ISOLATED_KEYS}
    env.update({
        "TG_DATA_DIR": str(data_dir),
        "TGQ_ENV_FILE": str(data_dir / ".env"),
        "TGQ_STARTUP_TIMEOUT": "90",
        "PYTHONUNBUFFERED": "1",
    })
    t0 = time.monotonic()
    proc2 = subprocess.Popen(
        [sys.executable, "-u", str(ROOT / "desktop.py")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, cwd=ROOT)
    try:
        outs, _ = proc2.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        proc2.kill()
        outs, _ = proc2.communicate(timeout=5)
    elapsed = time.monotonic() - t0
    check("second launch exits by itself", proc2.returncode == 0,
          f"code={proc2.returncode}")
    check("second launch is fast", elapsed < 10, f"{elapsed:.1f}s")
    check("second launch focuses the running window",
          "another instance" in (outs or "").lower(),
          f"output={ (outs or '')[:300] }")


# ---------------------------------------------------------------------------
# [8] console hygiene (evaluated last, covers everything)
# ---------------------------------------------------------------------------

def test_console() -> None:
    print("\n[8] console hygiene across all interactions")
    errors = [(ph, tx) for ph, ty, tx in CONSOLE if ty == "error"]
    warnings = [(ph, tx) for ph, ty, tx in CONSOLE if ty == "warning"]
    check("no console errors", len(errors) == 0,
          "; ".join(f"[{ph}] {tx}" for ph, tx in errors[:5]))
    check("no uncaught page errors", len(PAGE_ERRORS) == 0,
          "; ".join(PAGE_ERRORS[:5]))
    if warnings:
        print(f"  ....  {len(warnings)} console warning(s) (non-fatal):")
        for ph, tx in warnings[:5]:
            print(f"        [{ph}] {tx}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Telegram Query desktop E2E smoke test")
    ap.add_argument("--headed", action="store_true",
                    help="show the Playwright browser (default: headless)")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Install it with:")
        print("  pip install playwright && python -m playwright install chromium")
        return 1

    kill_stale_packaged_app()

    data_dir = Path(tempfile.mkdtemp(prefix="tgq-e2e-"))
    profile_dir = data_dir / "webview-profile"
    env_file = data_dir / ".env"
    print(f"data dir: {data_dir}")

    proc = None
    try:
        proc, port, _ = start_desktop(data_dir)
        base = f"http://127.0.0.1:{port}"
        print(f"desktop running on {base}")

        test_health(port)

        with sync_playwright() as p:
            ctx, page = open_ui(p, profile_dir, not args.headed,
                                "first-run")
            test_wizard(page, base, env_file)
            test_navigation(page, base)
            test_theme_language(page, base)

            # Release the window profile before quitting the app: the
            # restarted session must reopen the SAME profile (like the
            # real WebView2 window does), and a page polling a dead
            # server would only add console noise.
            ctx.close()

            # [5] quit + relaunch: the restarted instance stays running.
            proc, port, ctx, page = test_restart(
                p, data_dir, profile_dir, not args.headed, proc, port)

            # [6] while it runs, a second launch must hand off and exit.
            test_second_launch(data_dir)

            # [7] final graceful quit through the in-app Exit action.
            print("\n[7] final graceful quit via the in-app Exit action")
            ctx.close()
            exit_code = stop_desktop(proc, port, data_dir)
            check("graceful quit (Exit action), exit 0",
                  exit_code == 0, f"got={exit_code}")

        # [8] console hygiene across every interaction and both sessions
        test_console()

        print(f"\n{'=' * 60}")
        print(f"PASSED: {len(PASS)}   FAILED: {len(FAIL)}")
        if FAIL:
            print("Failures:")
            for f in FAIL:
                print(f"  - {f}")
            return 1
        return 0

    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait()
        shutil.rmtree(data_dir, ignore_errors=True)
        print(f"cleaned up {data_dir}")


if __name__ == "__main__":
    sys.exit(main())
