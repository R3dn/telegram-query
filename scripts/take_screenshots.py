"""Regenerate the documentation screenshots with synthetic data only.

Self-contained: seeds a fresh demo database (scripts/seed_demo.py - ten
fictional English groups), boots an isolated app instance whose environment
blocks the real .env (no real credentials, groups, or AI endpoints reach
it), then captures the README screenshots at high resolution with Playwright.

Requirements (dev-only, not runtime deps):
    pip install playwright && python -m playwright install chromium

Usage:
    python scripts/take_screenshots.py            # -> docs/screenshots/
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCREENSHOTS = ROOT / "docs" / "screenshots"

_BLOCKLIST = ROOT / "scripts" / "shot-blocklist.local.txt"


def _load_blocklist() -> list[str]:
    """Load personal identifiers that must never appear in screenshots.
    The file is kept outside the repo (gitignored) so real names and
    handles are never published.
    """
    blocklist: list[str] = []
    if _BLOCKLIST.exists():
        for line in _BLOCKLIST.read_text(encoding="utf-8").splitlines():
            entry = line.split("#", 1)[0].strip()
            if entry:
                blocklist.append(entry)
    else:
        print(
            f"  note: no blocklist found ({_BLOCKLIST.name}) — add one if you have"
            " real data on this machine that must not leak into docs/screenshots/"
        )
    return blocklist


FORBIDDEN = _load_blocklist()


def seed_demo(path: Path, messages: int) -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed_demo.py"),
         "--path", str(path), "--messages", str(messages)],
        check=True, capture_output=True)


def boot_app(port: int, db_path: Path) -> subprocess.Popen:
    """Boot an isolated instance: demo DB, no session, real .env blocked."""
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["TG_DB_PATH"] = str(db_path)
    env["TG_SESSION_PATH"] = str(db_path.parent / "shot-session")
    # explicit empties BLOCK the real .env from supplying values
    for k in ("TG_API_ID", "TG_API_HASH", "TELEGRAM_API_ID", "TELEGRAM_API_HASH"):
        env[k] = ""
    # fake AI config (display only - never called)
    env["AI_API_KEY"] = "sk-demo-not-a-real-key"
    env["AI_BASE_URL"] = "https://api.openai.com/v1"
    env["AI_MODEL"] = "gpt-4o-mini"
    return subprocess.Popen(
        [sys.executable, "app.py"], cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_up(port: int, proc: subprocess.Popen, timeout_s: float = 30) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health",
                                  timeout=2).read()
            return
        except Exception:
            if proc.poll() is not None:
                raise SystemExit(
                    "screenshot instance died on boot") from None
            time.sleep(0.5)
    raise SystemExit("screenshot instance never came up")


def assert_clean(page, label: str) -> None:
    text = page.inner_text("body")
    for bad in FORBIDDEN:
        assert bad not in text, f"{label}: real identifier visible: {bad!r}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8010)
    ap.add_argument("--messages", type=int, default=600)
    ap.add_argument("--dpr", type=float, default=1.5,
                    help="device scale factor (output = viewport * dpr)")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()

    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    demo_db = ROOT / "data" / "shot-demo.db"
    print("seeding synthetic demo archive ...", flush=True)
    seed_demo(demo_db, args.messages)

    print(f"booting isolated app on :{args.port} ...", flush=True)
    proc = boot_app(args.port, demo_db)
    try:
        wait_up(args.port, proc)

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(
                viewport={"width": args.width, "height": args.height},
                device_scale_factor=args.dpr,
                color_scheme="dark")
            page = ctx.new_page()
            base = f"http://127.0.0.1:{args.port}"

            def dismiss_wizard():
                page.wait_for_timeout(2500)
                if page.locator(".wizard").count():
                    page.click(".wizard-head .btn")

            def set_theme(theme: str):
                page.evaluate(f"localStorage.setItem('tgq-theme', '{theme}')")
                page.reload()
                page.wait_for_selector(".app")

            def open_discover(theme: str):
                """Load the app in discover mode (default landing view)."""
                page.goto(f"{base}/?shot")
                page.wait_for_selector(".app")
                set_theme(theme)
                dismiss_wizard()
                # wait for discover data (trending topics or empty state)
                page.wait_for_selector(".trend-row, .side-note")
                page.wait_for_timeout(600)

            def open_browse(theme: str):
                """Switch to Browse & search and wait for the feed."""
                page.goto(f"{base}/?shot")
                page.wait_for_selector(".app")
                set_theme(theme)
                dismiss_wizard()
                page.locator("button:has-text('Browse')").first.click()
                page.wait_for_selector(".msg-card")
                page.wait_for_timeout(600)

            def save(name: str):
                assert_clean(page, name)
                out = SCREENSHOTS / f"{name}.png"
                page.screenshot(path=str(out))
                print(f"  {name}: {out.relative_to(ROOT)}", flush=True)

            # 1) onboarding wizard (fresh profile -> auto-opens, dark default)
            page.goto(f"{base}/?shot=onboarding")
            page.wait_for_selector(".wizard")
            page.wait_for_selector("#tg-api-id")
            page.wait_for_timeout(400)
            save("onboarding")

            # 2) Discover view (dark) — the new landing view since v0.7
            open_discover("dark")
            save("discover-dark")

            # 3) Browse feed (dark)
            open_browse("dark")
            assert page.locator(".group-row").count() == 11  # 10 groups + All
            save("feed-dark")

            # 4) search with highlighting
            page.fill(".searchbox input", "discount")
            page.press(".searchbox input", "Enter")
            page.wait_for_selector("mark")
            page.wait_for_timeout(800)
            save("search")

            # 5) Discover view (light)
            open_discover("light")
            save("discover-light")

            # 6) Browse feed (light)
            open_browse("light")
            save("feed-light")

            browser.close()

        print("all screenshots captured with synthetic data only", flush=True)
    finally:
        proc.kill()
        for suffix in ("", "-wal", "-shm"):
            Path(str(demo_db) + suffix).unlink(missing_ok=True)
    print("instance stopped, demo db removed", flush=True)


if __name__ == "__main__":
    main()
