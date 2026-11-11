"""Desktop runtime for packaged Telegram Query builds (PyInstaller).

Source runs keep ``python app.py`` untouched. This module is what
``TelegramQuery.exe`` runs instead: a windowed, no-console application
lifecycle that

1. takes a single-instance lock (a second launch focuses the running one),
2. migrates any legacy archive found beside the exe into the user data
   dir (see :mod:`migration`),
3. writes logs to ``<data>/logs/app.log`` (rotating),
4. starts Uvicorn in a worker thread bound to ``127.0.0.1`` - a non-
   loopback HOST in the .env is overridden with a loud warning,
5. picks a free port when the preferred one is busy,
6. waits for ``/api/health/ready`` (never a blind sleep), then opens the
   application URL in the default browser,
7. keeps running until the user quits explicitly (``POST /api/app/quit``
   from the UI sets the quit event),
8. shuts down gracefully - Uvicorn stop, FastAPI lifespan cancellation
   of running jobs, scheduler stop - and never leaves orphan processes.

Everything degrades honestly: startup failures show a native error dialog
pointing at the log file, and the process exits with a nonzero code.
"""
from __future__ import annotations

import atexit
import ctypes
import io
import json
import logging
import logging.handlers
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

# When this script is the PyInstaller entry point, it runs as __main__.
# Any module that later imports 'desktop' must get the same object,
# otherwise globals (e.g. the quit event) are duplicated and the
# POST /api/app/quit endpoint can't reach the real runtime.
if __name__ == "__main__":
    sys.modules.setdefault("desktop", sys.modules["__main__"])

import config

log = logging.getLogger("tgq.desktop")

QUIT = threading.Event()
_RUNNING = threading.Event()          # this process owns a desktop run
_MUTEX: int | None = None             # single-instance mutex handle

APP_URL = ""                          # e.g. http://127.0.0.1:8412/
LOG_FILE = ""

_LOOPBACK = ("127.0.0.1", "localhost", "::1")
_ERROR_ALREADY_EXISTS = 183
_MB_ICONERROR = 0x00000010
_MB_ICONINFORMATION = 0x00000040

RUNTIME_FILE = "runtime.json"         # inside the data dir


def is_desktop() -> bool:
    """True when this process is the packaged desktop app (has a quit
    listener attached). The UI uses this to show the Exit action."""
    return _RUNNING.is_set()


def request_quit() -> bool:
    """Ask the desktop runtime to stop (called by POST /api/app/quit).
    Returns False when no desktop runtime is driving this process (a
    source-run dev server) - the endpoint reports that honestly."""
    if not _RUNNING.is_set():
        return False
    QUIT.set()
    return True


# ---------------------------------------------------------------------------
# Streams, logging, crash visibility (windowed apps have no console)
# ---------------------------------------------------------------------------

def ensure_streams() -> None:
    """Windowed PyInstaller apps get ``sys.stdout is None``; give them
    devnull-backed streams so libraries that write directly never crash."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name, None) is None:
            try:
                setattr(sys, name, io.TextIOWrapper(
                    open(os.devnull, "w"),
                    encoding="utf-8", errors="replace"))
            except OSError:
                pass


def configure_logging() -> str:
    """Rotating file log under ``<data>/logs`` + console echo when one
    exists. Installed BEFORE anything imports the app so every module's
    output lands in the file. Returns the log file path."""
    global LOG_FILE
    logs_dir = config.DATA_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    LOG_FILE = str(logs_dir / "app.log")
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5_000_000, backupCount=10, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(config.settings.log_level)
    root.addHandler(handler)
    # dev convenience: running desktop mode from a real console
    real_err = getattr(sys, "__stderr__", None)
    if real_err is not None and not real_err.closed:
        root.addHandler(logging.StreamHandler(real_err))
    return LOG_FILE


def _excepthook(exc_type, exc, tb) -> None:
    log.critical("unhandled exception", exc_info=(exc_type, exc, tb))


def install_excepthooks() -> None:
    sys.excepthook = _excepthook
    def _thread_hook(args):  # noqa: E306 - closure over nothing
        log.critical("unhandled exception in thread %s",
                     args[0].name if args[0] else "?",
                     exc_info=(args[1], args[2], args[3]))
    threading.excepthook = _thread_hook


# ---------------------------------------------------------------------------
# Single instance
# ---------------------------------------------------------------------------

def acquire_single_instance() -> bool:
    """Named-mutex single-instance guard (per login session, no admin).
    Returns False when another instance already holds the mutex."""
    global _MUTEX
    if sys.platform != "win32":
        return True                       # source runs elsewhere keep plain app.py
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.CreateMutexW(None, False,
                                       "Local\\TelegramQuery.SingleInstance")
        if not handle:
            log.warning("CreateMutexW failed (err=%s) - continuing without "
                        "a single-instance guard", ctypes.get_last_error())
            return True
        if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        _MUTEX = handle

        def _release():
            try:
                kernel32.CloseHandle(_MUTEX)
            except Exception:  # noqa: BLE001 - best effort at process exit
                pass
        atexit.register(_release)
        return True
    except Exception:                     # pragma: no cover - OS failure
        log.exception("single-instance guard failed - continuing")
        return True


# ---------------------------------------------------------------------------
# Runtime file (port + pid discovery for second launches)
# ---------------------------------------------------------------------------

def runtime_path() -> Path:
    return config.DATA_DIR / RUNTIME_FILE


def write_runtime_file(port: int) -> None:
    runtime_path().parent.mkdir(parents=True, exist_ok=True)
    runtime_path().write_text(json.dumps({
        "port": port, "pid": os.getpid(),
        "started": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "version": config.__version__,
    }, indent=2), encoding="utf-8")


def read_runtime_port() -> int | None:
    try:
        data = json.loads(runtime_path().read_text(encoding="utf-8"))
        return int(data["port"])
    except (OSError, ValueError, KeyError):
        return None


# ---------------------------------------------------------------------------
# Health, browser, dialogs
# ---------------------------------------------------------------------------

def _get(url: str, timeout: float = 2.0) -> tuple[bool, int, str]:
    """(ok, status, last-error) for a GET; ok=True only on HTTP 200."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200, resp.status, ""
    except urllib.error.HTTPError as e:
        return False, e.code, str(e)
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return False, 0, str(e)


def wait_healthy(port: int, timeout_s: float) -> tuple[bool, str]:
    """Poll the readiness endpoint until it answers 200 or the deadline
    passes. Never a blind sleep - every loop probes the real endpoint."""
    url = f"http://127.0.0.1:{port}/api/health/ready"
    deadline = time.monotonic() + timeout_s
    last_err = "not reachable"
    while time.monotonic() < deadline and not QUIT.is_set():
        ok, _status, err = _get(url)
        if ok:
            return True, ""
        last_err = err or last_err
        time.sleep(0.25)
    return False, last_err


def open_app(url: str) -> bool:
    try:
        opened = webbrowser.open(url)
    except Exception:  # noqa: BLE001 - exotic default-browser setups
        opened = False
    if not opened:
        log.warning("could not open the default browser - open %s manually",
                    url)
    return opened


def show_error(title: str, message: str) -> None:
    """Native error dialog (windowed app: no console to print to)."""
    if sys.platform != "win32":
        print(f"{title}: {message}", file=sys.stderr)
        return
    try:
        ctypes.windll.user32.MessageBoxW(
            0, message, f"Telegram Query - {title}", _MB_ICONERROR)
    except Exception:  # noqa: BLE001 - never crash on the error reporter
        pass


def show_info(title: str, message: str) -> None:
    if sys.platform != "win32":
        print(f"{title}: {message}")
        return
    try:
        ctypes.windll.user32.MessageBoxW(
            0, message, f"Telegram Query - {title}", _MB_ICONINFORMATION)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Port selection
# ---------------------------------------------------------------------------

def pick_port(preferred: int) -> tuple[int, bool]:
    """(port, kept_preferred). A busy preferred port means a foreign
    process owns it (the single-instance mutex rules out our own app), so
    we fall back to a free ephemeral port instead of failing."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", preferred))
        return preferred, True
    except OSError:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1], False


def _startup_timeout() -> float:
    try:
        return max(5.0, float(os.environ.get("TGQ_STARTUP_TIMEOUT", "60")))
    except ValueError:
        return 60.0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    global APP_URL
    ensure_streams()
    configure_logging()
    install_excepthooks()
    argv = list(sys.argv[1:] if argv is None else argv)
    no_browser = ("--no-browser" in argv
                  or bool(os.environ.get("TGQ_NO_BROWSER")))
    log.info("Telegram Query %s (desktop mode, pid %s, data dir %s)",
             config.__version__, os.getpid(), config.DATA_DIR)

    if not acquire_single_instance():
        log.info("another instance is running - focusing it")
        focus_existing(no_browser=no_browser)
        return 0

    # Legacy archive migration must happen before the DB is opened.
    try:
        import migration
        if migration.auto_migrate() is not None:
            config.reload_settings()   # pick up migrated credentials/.env
    except Exception:  # noqa: BLE001 - reported, never silent
        log.exception("data migration failed")
        show_error(
            "Startup failed",
            "Moving your existing archive into the application data "
            f"folder failed. Your original files were not modified.\n\n"
            f"Details are in the log:\n{LOG_FILE}")
        return 1

    # Import the app (db.init_db runs here, on the migrated database).
    try:
        import app as app_module
    except Exception:  # noqa: BLE001 - reported, never silent
        log.exception("application import failed")
        show_error(
            "Startup failed",
            "The application backend failed to initialize.\n\n"
            f"Details are in the log:\n{LOG_FILE}")
        return 1

    host = "127.0.0.1"
    if config.settings.host not in _LOOPBACK:
        log.warning("desktop mode forces a loopback bind - ignoring "
                    "HOST=%s (the API exposes your full archive)",
                    config.settings.host)
    port, kept = pick_port(config.settings.port)
    if not kept:
        log.warning("port %s is busy - using %s instead",
                    config.settings.port, port)
    APP_URL = f"http://{host}:{port}/"
    write_runtime_file(port)

    import uvicorn
    server = uvicorn.Server(uvicorn.Config(
        app_module.app, host=host, port=port,
        log_config=None,           # use the root logger -> app.log
        access_log=False))
    server_thread = threading.Thread(target=server.run, name="tgq-server",
                                     daemon=True)
    server_thread.start()
    _RUNNING.set()

    healthy, err = wait_healthy(port, _startup_timeout())
    if not healthy:
        log.error("backend did not become ready in %.0fs: %s",
                  _startup_timeout(), err)
        QUIT.set()
        server.should_exit = True
        server_thread.join(timeout=10)
        show_error(
            "Startup failed",
            "The application backend did not start within the expected "
            "time.\n\n"
            f"Details are in the log:\n{LOG_FILE}")
        return 1

    log.info("ready - application running at %s", APP_URL)
    if not no_browser:
        open_app(APP_URL)

    # Run until the user explicitly exits (UI Exit action) or the server
    # thread dies unexpectedly.
    while not QUIT.is_set():
        if not server_thread.is_alive():
            log.error("server thread exited unexpectedly")
            show_error(
                "The application stopped unexpectedly",
                "The local backend exited. Please start Telegram Query "
                f"again.\n\nDetails are in the log:\n{LOG_FILE}")
            return 1
        QUIT.wait(0.5)

    log.info("quit requested - shutting down gracefully")
    server.should_exit = True           # uvicorn runs the FastAPI lifespan:
    server_thread.join(timeout=20)      # job cancel + scheduler stop happen
    if server_thread.is_alive():
        log.error("graceful shutdown timed out - forcing exit "
                  "(SQLite checkpoints make this safe)")
        logging.shutdown()
        os._exit(1)
    logging.shutdown()
    return 0


def focus_existing(no_browser: bool = False) -> bool:
    """Second launch: wait briefly for the running instance to answer,
    then open the app URL next to it. A stale runtime file (crashed
    first instance) degrades to an honest error dialog."""
    for _ in range(30):                  # ~15s: big archives migrate slowly
        port = read_runtime_port()
        if port:
            ok, _status, _err = _get(
                f"http://127.0.0.1:{port}/api/health/ready")
            if ok:
                if not no_browser:
                    open_app(f"http://127.0.0.1:{port}/")
                return True
        time.sleep(0.5)
    show_error(
        "Telegram Query is already running",
        "Another instance appears to be starting or is not responding.\n"
        "If you just closed it, wait a few seconds and launch again.\n\n"
        f"Diagnostic log:\n{LOG_FILE}")
    return False


if __name__ == "__main__":
    sys.exit(main())
