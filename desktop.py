"""Desktop runtime for packaged Telegram Query builds (PyInstaller).

Source runs keep ``python app.py`` untouched. This module is what
``TelegramQuery.exe`` runs instead: a windowed, no-console application
lifecycle that

1. takes a single-instance lock (a second launch focuses the running
   window),
2. migrates any legacy archive found beside the exe into the user data
   dir (see :mod:`migration`),
3. writes logs to ``<data>/logs/app.log`` (rotating),
4. starts Uvicorn in a worker thread bound to ``127.0.0.1`` - a non-
   loopback HOST in the .env is overridden with a loud warning,
5. picks a free port when the preferred one is busy,
6. waits for ``/api/health/ready`` (never a blind sleep), then opens the
   application UI in its own native window (pywebview + Edge WebView2).
   If the runtime is missing or the window cannot start the process
   exits with an honest error dialog instead of a broken window,
7. keeps running until the user closes the window or quits explicitly
   (``POST /api/app/quit`` from the UI sets the quit event),
8. shuts down gracefully - window close, Uvicorn stop, FastAPI lifespan
   cancellation of running jobs, scheduler stop - and never leaves
   orphan processes.
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

_TRAY = None                          # system tray icon handle

APP_URL = ""                          # e.g. http://127.0.0.1:8412/
LOG_FILE = ""

_LOOPBACK = ("127.0.0.1", "localhost", "::1")
_ERROR_ALREADY_EXISTS = 183
_MB_ICONERROR = 0x00000010
_MB_ICONINFORMATION = 0x00000040
_SW_RESTORE = 9                      # Win32 ShowWindow: un-minimize

RUNTIME_FILE = "runtime.json"         # inside the data dir

# ---------------------------------------------------------------------------
# UI delivery: native window only (no browser fallback)
# ---------------------------------------------------------------------------

UI_WINDOW = "window"                  # native app window (pywebview)
UI_NONE = "none"                      # headless (tests, CI)

WINDOW_TITLE = "Telegram Query"       # matches the frontend <title>; a
                                      # second launch finds the window by it
WINDOW_SIZE = (1400, 900)
WINDOW_MIN_SIZE = (960, 600)
WINDOW_BACKGROUND = "#0b0e13"         # the UI's dark canvas (--bg): no
                                      # white flash before React mounts
# Microsoft EdgeUpdate channel GUIDs for the WebView2 runtime family -
# the Evergreen runtime plus the beta/dev/canary channels pywebview also
# accepts (its edgechromium backend needs build >= 86.0.622.0).
_WEBVIEW2_CHANNELS = (
    "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",   # Evergreen runtime
    "{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}",   # beta
    "{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}",   # developer
    "{65C35B14-6C1D-4122-AC46-7148CC9D6497}",   # canary
)
_WEBVIEW2_MIN = (86, 0)               # pywebview's floor for the window


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


def ui_mode(argv: list[str] | None = None) -> str:
    """How this run presents its UI: :data:`UI_WINDOW` (native app
    window) or :data:`UI_NONE` (headless - tests and CI).
    ``--no-window``/``TGQ_NO_WINDOW`` forces headless mode; legacy
    ``--no-browser``/``TGQ_NO_BROWSER`` are still honoured as aliases."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if ("--no-window" in argv or "--no-browser" in argv
            or os.environ.get("TGQ_NO_WINDOW")
            or os.environ.get("TGQ_NO_BROWSER")):
        return UI_NONE
    return UI_WINDOW


def webview2_runtime_version() -> tuple[bool, str]:
    """``(installed, detail)`` for the Edge WebView2 runtime the native
    window needs. Mirrors pywebview's own detection (any EdgeUpdate
    channel with build >= 86); a missing runtime must NOT reach pywebview,
    which would silently pick the legacy MSHTML renderer that cannot run
    the React UI."""
    if sys.platform != "win32":
        return True, "non-Windows: native OS webview"
    try:
        import winreg
    except ImportError:              # pragma: no cover - win32 always has it
        return False, "winreg unavailable"
    for channel in _WEBVIEW2_CHANNELS:
        for hive_name in ("HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE"):
            for subkey in (
                    rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{channel}",
                    rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{channel}"):
                try:
                    with winreg.OpenKey(getattr(winreg, hive_name),
                                        subkey) as key:
                        pv = winreg.QueryValueEx(key, "pv")[0].strip()
                except OSError:
                    continue
                if not pv or pv == "0.0.0.0":
                    continue
                try:
                    parts = tuple(int(p) for p in pv.split(".")[:2])
                except ValueError:
                    continue
                if parts >= _WEBVIEW2_MIN:
                    return True, f"WebView2 {pv}"
    return False, "no WebView2 runtime channel found (EdgeUpdate)"


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


def write_runtime_file(port: int, ui: str) -> None:
    runtime_path().parent.mkdir(parents=True, exist_ok=True)
    runtime_path().write_text(json.dumps({
        "port": port, "pid": os.getpid(), "ui": ui,
        "started": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "version": config.__version__,
    }, indent=2), encoding="utf-8")


def read_runtime_port() -> int | None:
    try:
        data = json.loads(runtime_path().read_text(encoding="utf-8"))
        return int(data["port"])
    except (OSError, ValueError, KeyError):
        return None


def read_runtime_ui() -> str:
    """UI mode the running instance recorded. Runtime files written by
    pre-v1.1 builds have no ``ui`` field - default to the native window."""
    try:
        data = json.loads(runtime_path().read_text(encoding="utf-8"))
        ui = data.get("ui")
        return ui if ui in (UI_WINDOW, UI_NONE) else UI_WINDOW
    except (OSError, ValueError):
        return UI_WINDOW


# ---------------------------------------------------------------------------
# Health, window, browser, dialogs
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


def wait_healthy(port: int, timeout_s: float,
                 server_thread: threading.Thread | None = None
                 ) -> tuple[bool, str]:
    """Poll the readiness endpoint until it answers 200 or the deadline
    passes. Never a blind sleep - every loop probes the real endpoint.
    When *server_thread* is given, a thread that dies during startup is
    reported within one poll interval instead of burning the whole
    startup timeout (uvicorn exits on a failed bind / startup crash; the
    health probe alone would just time out)."""
    url = f"http://127.0.0.1:{port}/api/health/ready"
    deadline = time.monotonic() + timeout_s
    last_err = "not reachable"
    while time.monotonic() < deadline and not QUIT.is_set():
        if server_thread is not None and not server_thread.is_alive():
            return False, "the backend process exited during startup"
        ok, _status, err = _get(url)
        if ok:
            return True, ""
        last_err = err or last_err
        time.sleep(0.25)
    return False, last_err


def run_app_window(url: str,
                   server_thread: threading.Thread) -> tuple[bool, bool]:
    """Serve the UI inside a native window (pywebview + Edge WebView2).

    Blocks the main thread - a WinForms GUI loop requires it - until the
    window closes. Closing the window asks for the same graceful
    shutdown the in-app Exit action triggers. Returns
    ``(ran, server_died)``: ``ran=False`` means the window backend failed
    before or while starting (missing library, broken .NET, unwritable
    storage).
    """
    try:
        import webview
    except Exception:                       # noqa: BLE001
        log.exception("pywebview is not importable - no native window")
        return False, False

    server_died = threading.Event()

    # text_select=True: the default would inject a global user-select
    # none - unacceptable for an archive users copy from. The app's own
    # CSS governs selection instead.
    # fit_window_size: never larger than the primary work area (small
    # laptops, 125-150% scaling); pywebview does not clamp itself.
    win_w, win_h = fit_window_size(WINDOW_SIZE, WINDOW_MIN_SIZE)
    window = webview.create_window(
        WINDOW_TITLE, url,
        width=win_w, height=win_h,
        min_size=WINDOW_MIN_SIZE,
        background_color=WINDOW_BACKGROUND,
        text_select=True)
    window.events.closed += lambda: QUIT.set()

    # minimised -> hide from taskbar and rely on the tray icon
    def _on_minimized() -> None:           # noqa: E306
        try:
            window.hide()
        except Exception:
            pass
    try:
        window.events.minimized += _on_minimized
    except AttributeError:
        pass                             # older pywebview - minimise stays
                                         # on the taskbar, tray still works

    _start_tray(window)

    # The WinForms form inherits python.exe's icon; swap in the app mark
    # for both taskbar and title bar once the handle exists.
    threading.Thread(target=_set_taskbar_icon, name="tgq-taskbar-icon",
                     daemon=True).start()

    def _watchdog() -> None:
        while not QUIT.wait(0.5):
            if not server_thread.is_alive():
                log.error("server thread exited unexpectedly")
                server_died.set()
                QUIT.set()
        _stop_tray()
        try:
            window.destroy()     # no-op when the window is already closed
        except Exception:         # noqa: BLE001 - best effort close
            log.exception("closing the window after quit failed")

    threading.Thread(target=_watchdog, name="tgq-window-watch",
                     daemon=True).start()
    try:
        webview.start(private_mode=False,
                      storage_path=str(config.DATA_DIR / "webview"))
    except Exception:                       # noqa: BLE001
        log.exception("native window failed to start")
        _stop_tray()
        return False, False
    _stop_tray()
    return True, server_died.is_set()


# ---------------------------------------------------------------------------
# System tray (minimize-to-tray)
# ---------------------------------------------------------------------------

def _icon_path() -> Path:
    """Resolved path to the app icon (.ico), or nonexistent if missing."""
    repo = Path(__file__).resolve().parent
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "packaging" / "windows" / "assets" / "app.ico"
    return repo / "packaging" / "windows" / "assets" / "app.ico"


def _tray_icon_image():
    """Load the app icon as a PIL Image for the system tray."""
    from PIL import Image
    ico_path = _icon_path()
    if not ico_path.exists():
        log.warning("icon file not found at %s - using placeholder",
                    ico_path)
        return Image.new("RGBA", (64, 64), (91, 141, 239, 255))
    # ICO is multi-frame; use the largest frame for the tray
    img = Image.open(ico_path)
    frames = []
    try:
        while True:
            frames.append(img.copy())
            img.seek(img.tell() + 1)
    except EOFError:
        pass
    if frames:
        return max(frames, key=lambda f: f.size[0] * f.size[1])
    return img


def _windowed_interpreter(exe: str | None = None) -> str:
    """Interpreter for the Start-Menu shortcut: ``pythonw.exe`` when it
    exists next to *exe* (default: this interpreter).

    ``python.exe`` is a console program - a shortcut targeting it
    flashes a black terminal window on every launch, which closes the
    moment the process exits (or hands off to another instance), and
    looks exactly like "the app started and died". ``pythonw.exe`` runs
    the same script windowed (desktop.py gives it devnull-backed
    streams via ensure_streams). Frozen apps have no pythonw next to
    the exe and keep their own exe as the target."""
    exe_path = Path(exe or sys.executable)
    windowed = exe_path.with_name("pythonw.exe")
    return str(windowed) if windowed.exists() else str(exe_path)


def _shortcut_arguments() -> str:
    """The script path for the Start-Menu shortcut, QUOTED.

    Windows passes the Arguments field verbatim on the command line; a
    repo path containing spaces (e.g. ``E:\\AI Projects\\...``) must
    reach the interpreter as ONE argv token. Unquoted, pythonw opened
    ``E:\\AI`` as the script and exited instantly - the shortcut click
    did nothing, with no console and no error (python.exe at least
    flashed the error in a closing console)."""
    return f'"{Path(__file__).resolve()}"'


def _ensure_start_menu_shortcut(app_user_model_id: str,
                                icon_path: str) -> None:
    """Write/update a Start-Menu shortcut for Telegram Query.

    Windows uses this shortcut's icon when it groups the running window
    under the same AppUserModelID."""
    try:
        import win32com.client
    except Exception:
        return                         # pywin32 not installed — silent skip

    import os
    from pathlib import Path

    start_menu = Path(
        os.environ.get(
            "APPDATA",
            os.environ.get("USERPROFILE",
                           str(Path.home()))) + r"\Microsoft\Windows\Start Menu\Programs")
    shortcut_path = start_menu / "Telegram Query.lnk"
    start_menu.mkdir(parents=True, exist_ok=True)

    # Only create if missing or if target has changed
    needs_update = True
    if shortcut_path.exists():
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            sc = shell.CreateShortCut(str(shortcut_path))
            current_target = sc.Targetpath
            current_icon = sc.IconLocation
            # WSH cannot read back the AppUserModelID (that is why the
            # propsys patch below exists) - compare only what it CAN
            # read: target + icon. The target check makes the one-time
            # python.exe -> pythonw.exe migration rewrite the shortcut.
            if (current_target and
                _windowed_interpreter().upper() in current_target.upper()
                and current_icon and icon_path in current_icon):
                needs_update = False
        except Exception:
            pass

    if needs_update:
        shell = win32com.client.Dispatch("WScript.Shell")
        sc = shell.CreateShortCut(str(shortcut_path))
        # pythonw (never python.exe): the shortcut must not flash a
        # console window on every launch
        sc.Targetpath = _windowed_interpreter()
        # quoted: a script path with spaces is ONE argv token (see
        # _shortcut_arguments) - unquoted it never even started
        sc.Arguments = _shortcut_arguments()
        sc.WorkingDirectory = str(Path(__file__).resolve().parent)
        sc.IconLocation = icon_path + ",0"
        sc.Description = "Telegram Query"
        sc.WindowStyle = 1                     # normal window
        # System.AppUserModelID property bag is not exposed via WSH, so
        # we write the shortcut first then patch it via IShellLink.
        sc.Save()

        # Patch the AppUserModelID into the shortcut via IShellLink
        try:
            from win32com.propsys import propsys
            from win32com.propsys.pscon import PKEY_AppUserModel_ID

            # GPS_READWRITE may not be exposed; use its numeric value 2
            props = propsys.SHGetPropertyStoreFromParsingName(
                str(shortcut_path), None, 2, propsys.IID_IPropertyStore)
            props.SetValue(
                PKEY_AppUserModel_ID,
                propsys.PROPVARIANTType(app_user_model_id))
            props.Commit()
        except Exception:
            log.warning("could not set AppUserModelID on shortcut")


def _set_taskbar_icon() -> None:
    """Replace the taskbar icon with our own mark so a source run of
    desktop.py doesn't show the generic Python exe icon.

    Windows 10/11 taskbar groups windows by the executable's icon.  The
    only reliable override for a source run is:

    1. Create a Start-Menu shortcut that points at python.exe and
       carries our icon + an AppUserModelID.
    2. Call `SetCurrentProcessExplicitAppUserModelID` with the same ID
       so Windows pairs the running window with the shortcut.
    """
    if sys.platform != "win32":
        return

    ico_path = _icon_path()
    if not ico_path.exists():
        log.warning("icon file missing, taskbar icon unchanged")
        return

    app_user_model_id = "Redn.TelegramQuery.Desktop"

    try:
        _ensure_start_menu_shortcut(
            app_user_model_id, str(ico_path.resolve()))
    except Exception:
        log.exception("creating taskbar shortcut failed")

    # Force Windows to refresh the icon cache / taskbar association.
    try:
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED
    except Exception:
        pass

    try:
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        shell32.SetCurrentProcessExplicitAppUserModelID(
            ctypes.c_wchar_p(app_user_model_id))
    except Exception:
        log.exception("SetCurrentProcessExplicitAppUserModelID failed")

    # Classic per-window icon (title bar + Alt-Tab).
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)

        hicon_large = ctypes.c_void_p()
        hicon_small = ctypes.c_void_p()
        shell32.ExtractIconExW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_int,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint]
        shell32.ExtractIconExW.restype = ctypes.c_uint
        n = shell32.ExtractIconExW(
            str(ico_path), 0,
            ctypes.byref(hicon_large), ctypes.byref(hicon_small), 1)
        if n == 0 or not hicon_large.value:
            log.warning("ExtractIconExW could not load %s", ico_path)
            return

        hwnd = None
        for _ in range(60):
            hwnd = user32.FindWindowW(None, WINDOW_TITLE)
            if hwnd:
                break
            time.sleep(0.5)
        if not hwnd:
            return

        WM_SETICON = 0x0080
        ICON_BIG = 1
        ICON_SMALL = 0
        user32.SendMessageW.argtypes = [
            ctypes.c_void_p, ctypes.c_uint,
            ctypes.c_size_t, ctypes.c_void_p]
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG,
                            hicon_large.value)
        if hicon_small.value:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL,
                                hicon_small.value)

        # Set class icon (affects taskbar grouping).
        GCLP_HICON = -14
        user32.SetClassLongPtrW.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        user32.SetClassLongPtrW.restype = ctypes.c_void_p
        user32.SetClassLongPtrW(hwnd, GCLP_HICON, hicon_large.value)

        # Force frame refresh.
        SWP_FRAMECHANGED = 0x0020
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE |
                            SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)

        log.info("taskbar icon set from %s", ico_path)
    except Exception:
        log.exception("taskbar icon setup failed")


def _start_tray(window) -> None:
    """Start the system tray icon in a background thread."""
    global _TRAY
    try:
        import pystray
    except Exception:                       # noqa: BLE001
        log.exception("pystray not importable - system tray unavailable")
        return

    icon_img = _tray_icon_image()

    def _on_open(_icon, _item):            # noqa: E306
        try:
            window.show()
        except Exception:
            pass

    def _on_exit(_icon, item):              # noqa: E306
        QUIT.set()
        if _icon is not None:
            _icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Telegram Query", lambda _i, _it: None,
                         enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open", _on_open, default=True),
        pystray.MenuItem("Exit", _on_exit),
    )
    _TRAY = pystray.Icon("TelegramQuery", icon_img,
                         "Telegram Query", menu=menu)
    threading.Thread(target=_TRAY.run, name="tgq-tray",
                     daemon=True).start()


def _stop_tray() -> None:
    """Cleanly stop the system tray icon when the app exits."""
    global _TRAY
    if _TRAY is not None:
        try:
            _TRAY.stop()
        except Exception:                   # noqa: BLE001
            pass
        _TRAY = None


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
# Initial window placement (small screens / high-DPI)
# ---------------------------------------------------------------------------

_SM_CXFULLSCREEN = 16               # Win32: work-area width, primary screen
_SM_CYFULLSCREEN = 17               # Win32: work-area height, primary screen


def _primary_work_area() -> tuple[int, int] | None:
    """(width, height) of the primary monitor's work area in physical
    pixels (excludes the taskbar), or None off-Windows / on failure."""
    if sys.platform != "win32":
        return None
    try:
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(_SM_CXFULLSCREEN)
        h = user32.GetSystemMetrics(_SM_CYFULLSCREEN)
        return (w, h) if w > 0 and h > 0 else None
    except Exception:                     # noqa: BLE001 - metrics are optional
        return None


def _primary_scale() -> float:
    """DPI scale of the primary monitor (logical -> physical px)."""
    if sys.platform != "win32":
        return 1.0
    try:
        return max(1.0, ctypes.windll.user32.GetDpiForSystem() / 96.0)
    except Exception:                     # noqa: BLE001
        return 1.0


def fit_window_size(default: tuple[int, int],
                    minimum: tuple[int, int]) -> tuple[int, int]:
    """Clamp the initial window to the primary work area.

    pywebview's WinForms backend multiplies the requested logical size
    by the monitor DPI and never clamps to the screen, so the documented
    1400x900 default overflowed the window on 1366x768 laptops (either
    axis) and at 125-150% scaling on 1920x1080 displays (the window is
    physically larger than the screen). The clamped window still keeps
    the design size on any screen that fits it."""
    wa = _primary_work_area()
    if wa is None:
        return default
    scale = _primary_scale()
    max_w = int(wa[0] / scale)
    max_h = int(wa[1] / scale)
    w = min(default[0], max_w)
    h = min(default[1], max_h)
    # never shrink below the usable minimum unless the screen is even
    # smaller than the minimum itself (then the work area wins)
    return (max(w, min(minimum[0], max_w)),
            max(h, min(minimum[1], max_h)))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _report_server_death() -> None:
    show_error(
        "The application stopped unexpectedly",
        "The local backend exited. Please start Telegram Query "
        f"again.\n\nDetails are in the log:\n{LOG_FILE}")


def _startup_crash_dump(exc: BaseException) -> str:
    """Best-effort crash dump when even the log file is unavailable
    (unwritable data dir, full disk): %TEMP% keeps operator evidence.
    Returns the dump path, or '' when even that failed."""
    try:
        import tempfile
        import traceback
        path = (Path(tempfile.gettempdir())
                / "TelegramQuery-startup-error.log")
        path.write_text(
            f"Telegram Query {config.__version__} failed to start\n"
            f"pid={os.getpid()} data_dir={config.DATA_DIR}\n"
            f"{traceback.format_exc()}",
            encoding="utf-8", errors="replace")
        return str(path)
    except Exception:                     # noqa: BLE001 - best effort
        return ""


def _report_early_crash(exc: BaseException) -> None:
    """Startup failed before logging was up: the native dialog is the
    only honest report left, plus a %TEMP% dump."""
    dump = _startup_crash_dump(exc)
    show_error(
        "Startup failed",
        "Telegram Query could not create its data folder or log file:\n"
        f"{config.DATA_DIR}\n\n"
        f"({type(exc).__name__}: {exc})\n\n"
        "Free up disk space or check the folder's permissions, then "
        "start again."
        + (f"\n\nDetails were written to:\n{dump}" if dump else ""))


def main(argv: list[str] | None = None) -> int:
    global APP_URL
    ensure_streams()
    try:
        configure_logging()
    except Exception as e:                 # noqa: BLE001 - data dir unusable
        # windowed app: without this dialog the exe would die silently
        # (no console, no log file, nothing on screen)
        _report_early_crash(e)
        return 1
    install_excepthooks()
    try:
        return _run(argv)
    except Exception:                      # noqa: BLE001 - reported, never silent
        log.exception("desktop startup failed")
        show_error(
            "Startup failed",
            "The application failed to start.\n\n"
            f"Details are in the log:\n{LOG_FILE}")
        return 1


def _run(argv: list[str] | None = None) -> int:
    global APP_URL
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = ui_mode(argv)
    log.info("Telegram Query %s (desktop mode, ui=%s, pid %s, data dir %s)",
             config.__version__, mode, os.getpid(), config.DATA_DIR)

    if not acquire_single_instance():
        log.info("another instance is running - focusing it")
        focus_existing(quiet=(mode == UI_NONE))
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
    write_runtime_file(port, mode)

    import uvicorn
    server = uvicorn.Server(uvicorn.Config(
        app_module.app, host=host, port=port,
        log_config=None,           # use the root logger -> app.log
        access_log=False))
    server_thread = threading.Thread(target=server.run, name="tgq-server",
                                     daemon=True)
    server_thread.start()
    _RUNNING.set()

    healthy, err = wait_healthy(port, _startup_timeout(), server_thread)
    if not healthy:
        if err == "the backend process exited during startup":
            log.error("backend exited during startup - see the log above")
            QUIT.set()
            server.should_exit = True
            server_thread.join(timeout=10)
            show_error(
                "Startup failed",
                "The application backend exited during startup.\n\n"
                f"Details are in the log:\n{LOG_FILE}")
            return 1
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

    if mode == UI_NONE:
        # Headless runs (tests, CI): supervise inline until the user
        # exits (UI Exit action) or the server thread dies unexpectedly.
        while not QUIT.is_set():
            if not server_thread.is_alive():
                log.error("server thread exited unexpectedly")
                _report_server_death()
                return 1
            QUIT.wait(0.5)
    else:
        # Native window: mandatory WebView2 runtime.
        available, detail = webview2_runtime_version()
        if not available:
            log.error("native window unavailable (%s) - cannot start", detail)
            QUIT.set()
            server.should_exit = True
            server_thread.join(timeout=10)
            show_error(
                "Missing WebView2 Runtime",
                "The app window needs the Microsoft Edge WebView2 Runtime, "
                "which is not installed on this computer.\n\n"
                "Install the free runtime from\n\nhttps://aka.ms/webview2\n\n"
                "Details are in the log:\n" + LOG_FILE)
            return 1

        ran, server_died = run_app_window(APP_URL, server_thread)
        if not ran:
            log.error("native window failed to start - see the log above")
            QUIT.set()
            server.should_exit = True
            server_thread.join(timeout=10)
            show_error(
                "Window startup failed",
                "The application window could not open.\n\n"
                f"Details are in the log:\n{LOG_FILE}")
            return 1
        if server_died:
            _report_server_death()
            return 1

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


def _focus_existing_window(timeout_s: float = 10.0) -> bool:
    """Bring the running instance's native window to the front.

    Called from a second launch, which is the foreground process at
    that moment - exactly the case Windows allows to hand focus to
    another window. Returns False when no window appears within the
    deadline (still starting, or the first instance has none)."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
    except OSError:                       # pragma: no cover - OS failure
        return False
    user32.FindWindowW.restype = ctypes.c_void_p
    user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if hwnd:
            user32.ShowWindow(hwnd, _SW_RESTORE)
            user32.SetForegroundWindow(hwnd)   # best effort; restore
            return True                          # above already un-hides it
        time.sleep(0.5)
    return False


def focus_existing(quiet: bool = False) -> bool:
    """Second launch: wait briefly for the running instance to answer,
    then surface its window. A stale runtime file (crashed first instance)
    degrades to an honest error dialog."""
    for _ in range(30):                  # ~15s: big archives migrate slowly
        port = read_runtime_port()
        if port:
            ok, _status, _err = _get(
                f"http://127.0.0.1:{port}/api/health/ready")
            if ok:
                if not quiet:
                    _surface_running_instance(port)
                return True
        time.sleep(0.5)
    show_error(
        "Telegram Query is already running",
        "Another instance appears to be starting or is not responding.\n"
        "If you just closed it, wait a few seconds and launch again.\n\n"
        f"Diagnostic log:\n{LOG_FILE}")
    return False


def _surface_running_instance(port: int) -> None:
    """Focus the running instance's window - and never exit silently.

    A second launch that finds the instance alive must leave the user
    with something: the focused window, or an honest dialog. Exiting
    quietly is indistinguishable from "the app is broken" (the click
    appears to do nothing; with a console-mode launcher the terminal
    flashes and closes)."""
    ui = read_runtime_ui()
    if ui == UI_WINDOW and _focus_existing_window():
        return
    if ui == UI_NONE:
        show_error(
            "Telegram Query is already running",
            "Another Telegram Query instance is running headless on "
            f"this machine (port {port}; a test or background run).\n\n"
            "Close it - end the \"python.exe\" process running "
            "desktop.py in Task Manager - then start again.")
    else:
        show_error(
            "Telegram Query is already running",
            "Another Telegram Query instance is running, but its window "
            "did not appear within 10 seconds - it may still be "
            "starting or have stopped responding.\n\n"
            "If nothing appears, close Telegram Query from the "
            "notification area (or Task Manager) and start again.")


if __name__ == "__main__":
    sys.exit(main())
