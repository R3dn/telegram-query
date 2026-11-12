"""Tests for desktop.py - the packaged-app lifecycle primitives.

Everything is tested against real sockets/servers on loopback; the
things that must never run in tests (native dialogs, the real mutex,
spawning the server) are monkeypatched.
"""
import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import config
import desktop
import migration


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def reset_desktop_state():
    desktop.QUIT.clear()
    desktop._RUNNING.clear()
    yield
    desktop.QUIT.clear()
    desktop._RUNNING.clear()


@pytest.fixture()
def clean_root_logger():
    """Remove logging handlers a desktop.main() call added (its rotating
    file log must not leak into later tests on Windows)."""
    root = desktop.logging.getLogger()
    before = list(root.handlers)
    yield
    for h in root.handlers[:]:
        if h not in before:
            root.removeHandler(h)
            try:
                h.close()
            except Exception:                     # noqa: BLE001
                pass


# The erase action intentionally drops the app-managed credential env
# vars and rebuilds config.settings mid-process (that is the fix for
# "erase says configuration was deleted but the process still reports
# itself configured"). The rest of the test session expects the
# conftest-configured state back afterwards.
_CRED_KEYS = ("TG_API_ID", "TG_API_HASH", "TELEGRAM_API_ID",
              "TELEGRAM_API_HASH", "AI_API_KEY", "AI_BASE_URL",
              "AI_MODEL", "AI_MODEL_EXTRACT", "AI_MODEL_SYNTH",
              "AI_MODEL_EMBED")


@pytest.fixture()
def protect_credentials():
    saved_env = {k: os.environ.get(k) for k in _CRED_KEYS}
    saved_settings = config.settings
    yield
    for k, v in saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    config.settings = saved_settings


# ---------------------------------------------------------------------------
# Port selection
# ---------------------------------------------------------------------------

def test_pick_port_prefers_the_requested_port():
    port, kept = desktop.pick_port(18432)
    assert port == 18432 and kept is True


def test_pick_port_falls_back_when_busy():
    # hold the preferred port with a foreign process stand-in
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 18433))
        s.listen(1)
        port, kept = desktop.pick_port(18433)
    assert port != 18433 and kept is False
    # the fallback port is actually free
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))


# ---------------------------------------------------------------------------
# Runtime file (second-launch discovery)
# ---------------------------------------------------------------------------

def test_runtime_file_roundtrip(data_dir):
    desktop.write_runtime_file(18500, desktop.UI_WINDOW)
    raw = (data_dir / "runtime.json").read_text(encoding="utf-8")
    assert json.loads(raw)["port"] == 18500
    assert json.loads(raw)["ui"] == desktop.UI_WINDOW
    assert desktop.read_runtime_port() == 18500
    assert desktop.read_runtime_ui() == desktop.UI_WINDOW


def test_runtime_file_ui_modes_roundtrip(data_dir):
    for mode in (desktop.UI_WINDOW, desktop.UI_NONE):
        desktop.write_runtime_file(18501, mode)
        assert desktop.read_runtime_ui() == mode


def test_runtime_file_without_ui_defaults_to_window(data_dir):
    # pre-v1.1 runtime files have no "ui" field: default to window
    (data_dir / "runtime.json").write_text(
        '{"port": 8000, "pid": 1}', encoding="utf-8")
    assert desktop.read_runtime_ui() == desktop.UI_WINDOW


def test_runtime_file_garbage_ui_defaults_to_window(data_dir):
    (data_dir / "runtime.json").write_text(
        '{"port": 8000, "pid": 1, "ui": "hologram"}', encoding="utf-8")
    assert desktop.read_runtime_ui() == desktop.UI_WINDOW


def test_read_runtime_port_tolerates_garbage(data_dir):
    (data_dir / "runtime.json").write_text("{not json", encoding="utf-8")
    assert desktop.read_runtime_port() is None
    assert desktop.read_runtime_port() is None   # missing file


# ---------------------------------------------------------------------------
# Health checking (no blind sleeps)
# ---------------------------------------------------------------------------

def _serve(handler, port_holder):
    server = HTTPServer(("127.0.0.1", 0), handler)
    port_holder.append(server.server_address[1])
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_wait_healthy_succeeds_against_a_real_server():
    ports = []

    class _Ready(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - http.server API
            if self.path == "/api/health/ready":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok": true}')
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):     # silence the test output
            pass

    server = _serve(_Ready, ports)
    try:
        ok, err = desktop.wait_healthy(ports[0], timeout_s=5)
        assert ok is True and err == ""
    finally:
        server.shutdown()


def test_wait_healthy_times_out_with_the_real_error():
    # find a definitely-free port (nothing listens on it)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]
    ok, err = desktop.wait_healthy(free_port, timeout_s=1.2)
    assert ok is False
    assert err  # the real connection error, not a silent blank


# ---------------------------------------------------------------------------
# Quit semantics
# ---------------------------------------------------------------------------

def test_quit_requires_a_desktop_runtime(reset_desktop_state):
    assert desktop.is_desktop() is False
    assert desktop.request_quit() is False
    assert desktop.QUIT.is_set() is False


def test_quit_sets_the_event_when_running(reset_desktop_state):
    desktop._RUNNING.set()
    assert desktop.is_desktop() is True
    assert desktop.request_quit() is True
    assert desktop.QUIT.is_set() is True


def test_quit_endpoint_honest_in_source_mode(api_client, reset_desktop_state):
    resp = api_client.post("/api/app/quit")
    assert resp.status_code == 409
    assert "source run" in resp.json()["error"]


def test_quit_endpoint_stops_the_desktop_runtime(api_client,
                                                 reset_desktop_state):
    desktop._RUNNING.set()
    resp = api_client.post("/api/app/quit")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert desktop.QUIT.is_set() is True


def test_app_state_reports_desktop_mode(api_client, reset_desktop_state):
    resp = api_client.get("/api/app/state").json()
    assert resp["desktop_mode"] is False
    desktop._RUNNING.set()
    resp = api_client.get("/api/app/state").json()
    assert resp["desktop_mode"] is True


# ---------------------------------------------------------------------------
# Streams + logging
# ---------------------------------------------------------------------------

def test_configure_logging_writes_to_data_dir(data_dir):
    path = desktop.configure_logging()
    assert path.endswith("app.log")
    assert (data_dir / "logs" / "app.log").exists()
    desktop.log.info("hello from the desktop test")
    for h in desktop.logging.getLogger().handlers[:]:
        if getattr(h, "baseFilename", "").endswith("app.log"):
            desktop.logging.getLogger().removeHandler(h)
            h.close()


def test_ensure_streams_replaces_none():
    import sys as _sys
    old_out, old_err = _sys.stdout, _sys.stderr
    try:
        _sys.stdout = None
        _sys.stderr = None
        desktop.ensure_streams()
        assert _sys.stdout is not None and _sys.stderr is not None
        _sys.stdout.write("still works\n")     # must not raise
        injected = (_sys.stdout, _sys.stderr)
    finally:
        _sys.stdout, _sys.stderr = old_out, old_err
        for stream in injected:
            try:
                stream.close()
            except Exception:  # noqa: BLE001 - best effort cleanup
                pass


# ---------------------------------------------------------------------------
# Data endpoints (status / import / erase)
# ---------------------------------------------------------------------------

def _make_source_archive(path, messages: int = 2):
    """A small real archive used by the import-endpoint test."""
    import db
    path.mkdir(parents=True, exist_ok=True)
    conn = db.get_db(str(path / migration.DB_NAME))
    try:
        db.upsert_chat(conn, -100777, "Import Group", "imp", "group")
        for i in range(messages):
            db.upsert_message(conn, -100777, 10 + i,
                              f"2026-11-1{i}T09:00:00+00:00", 1, "s",
                              f"imported {i}")
        conn.commit()
    finally:
        conn.close()
    return path


def test_data_status_shape(api_client):
    resp = api_client.get("/api/data/status").json()
    assert resp["desktop_mode"] is False
    assert "data_dir" in resp and "db_size" in resp
    assert "session_exists" in resp and "migrations" in resp


def test_data_import_requires_a_real_folder(api_client):
    resp = api_client.post("/api/data/import",
                           json={"source_dir": "Z:/does/not/exist"})
    assert resp.status_code == 400
    assert "No such folder" in resp.json()["error"]


def test_data_erase_requires_confirmation(api_client):
    resp = api_client.post("/api/data/erase", json={"confirm": "no"})
    assert resp.status_code == 400
    assert "ERASE" in resp.json()["error"]
    # the archive is untouched
    resp = api_client.get("/api/app/state").json()
    assert isinstance(resp["messages"], int)


def test_data_erase_deletes_archive_but_keeps_logs(api_client, tmp_path,
                                                   monkeypatch,
                                                   protect_credentials):
    data = tmp_path / "erase-test"
    data.mkdir()
    # an isolated archive under the test data dir
    (data / migration.DB_NAME).write_bytes(b"db")
    (data / migration.SESSION_NAME).write_bytes(b"session")
    (data / ".env").write_text("TG_API_ID=1\n", encoding="utf-8")
    (data / "runtime.json").write_text("{}", encoding="utf-8")
    (data / "migration-report.json").write_text("[]", encoding="utf-8")
    (data / "backups").mkdir()
    (data / "backups" / "old.db").write_bytes(b"x")
    (data / "logs").mkdir()
    (data / "logs" / "app.log").write_text("kept", encoding="utf-8")

    monkeypatch.setattr(config.settings, "data_dir", data)
    monkeypatch.setattr(config.settings, "db_path", data / migration.DB_NAME)
    monkeypatch.setattr(config.settings, "session_path",
                        data / migration.SESSION_NAME)
    monkeypatch.setattr(config, "ENV_FILE", data / ".env")

    resp = api_client.post("/api/data/erase", json={"confirm": "ERASE"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert set(body["deleted"]) >= {migration.DB_NAME, migration.SESSION_NAME,
                                    ".env", "backups/"}
    # explicit targets only: the log survives as the operator's evidence
    assert (data / "logs" / "app.log").read_text(encoding="utf-8") == "kept"
    assert not (data / migration.DB_NAME).exists()
    assert not (data / "backups").exists()


def test_data_erase_recreates_a_working_empty_archive(
        api_client, tmp_path, monkeypatch, protect_credentials):
    """Regression (v1.0.3): the erase action deletes the database file
    but the UI reloads into the SAME process ~1.5s later. db.get_db()'s
    one-time schema guard then made the next connection re-create an
    empty file with NO tables - readiness 503 and every DB endpoint 500
    until the app was restarted. The erase flow must leave a fresh,
    schema-complete empty archive, and - the .env was erased too - the
    process must honestly report itself as unconfigured."""
    import db as db_mod
    # keep the real repo .env out of the deletion (test isolation: the
    # endpoint erases whatever config.ENV_FILE points at)
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "no.env")
    # isolate the session path: the app lifespan's background auth check
    # opens a TelegramClient on the real session file (a real network
    # handshake that outlives the request) - erasing under it is an honest
    # 409 in production, and the test must not depend on that timing
    monkeypatch.setattr(config.settings, "session_path",
                        tmp_path / "erase-session")
    # seed the session archive: one chat + one message
    c = db_mod.get_db()
    try:
        db_mod.upsert_chat(c, -100999, "Erase Repro", "er", "group")
        db_mod.upsert_message(c, -100999, 1, "2026-01-01T00:00:00+00:00",
                              1, "s", "erase me")
        c.commit()
    finally:
        c.close()
    resp = api_client.get("/api/app/state")
    assert resp.status_code == 200
    assert resp.json()["messages"] == 1

    resp = api_client.post("/api/data/erase", json={"confirm": "ERASE"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True

    # the exact request the reloaded UI makes first: readiness must be
    # 200 with a REAL database again (schema included), never 503/500
    resp = api_client.get("/api/health/ready")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True and body["checks"]["db"] is True
    assert body["telegram_configured"] is False   # config was erased too

    resp = api_client.get("/api/app/state")
    assert resp.status_code == 200, resp.text
    state = resp.json()
    assert state["messages"] == 0
    assert state["telegram_configured"] is False

    # the fresh schema is really functional (search needs the FTS table)
    resp = api_client.get("/api/search", params={"q": "anything"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_data_erase_rejected_while_a_job_runs(api_client,
                                              protect_credentials):
    """A running job holds the archive (and the Telegram session) - the
    erase must refuse rather than delete files under a live job."""
    from jobs import JOBS
    with JOBS.lock:
        JOBS.running = True
        JOBS.name = "sync"
    try:
        resp = api_client.post("/api/data/erase", json={"confirm": "ERASE"})
        assert resp.status_code == 409
    finally:
        with JOBS.lock:
            JOBS.running = False
            JOBS.name = ""
    # nothing was deleted
    resp = api_client.get("/api/health/ready")
    assert resp.status_code == 200


def test_data_import_into_empty_archive(api_client, tmp_path, monkeypatch):
    """End-to-end through the API: build a source archive, import it into
    the (empty) test archive via the endpoint."""
    source = _make_source_archive(tmp_path / "import-src", messages=2)
    # keep the real repo .env out of the settings reload
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "no.env")
    # the conftest session DB is empty -> importable
    resp = api_client.post("/api/data/import",
                           json={"source_dir": str(source)})
    assert resp.status_code == 200, resp.text
    assert resp.json()["migration"]["status"] == "ok"
    state = api_client.get("/api/app/state").json()
    assert state["messages"] == 2


# ---------------------------------------------------------------------------
# UI delivery: native window vs browser fallback vs headless
# ---------------------------------------------------------------------------

def test_ui_mode_defaults_to_the_native_window(monkeypatch):
    for var in ("TGQ_NO_WINDOW", "TGQ_NO_BROWSER"):
        monkeypatch.delenv(var, raising=False)
    assert desktop.ui_mode([]) == desktop.UI_WINDOW


def test_ui_mode_headless_via_flags_and_env(monkeypatch):
    for var in ("TGQ_NO_WINDOW", "TGQ_NO_BROWSER"):
        monkeypatch.delenv(var, raising=False)
    assert desktop.ui_mode(["--no-window"]) == desktop.UI_NONE
    assert desktop.ui_mode(["--no-browser"]) == desktop.UI_NONE  # legacy
    monkeypatch.setenv("TGQ_NO_WINDOW", "1")
    assert desktop.ui_mode([]) == desktop.UI_NONE
    monkeypatch.delenv("TGQ_NO_WINDOW")
    monkeypatch.setenv("TGQ_NO_BROWSER", "1")                    # legacy
    assert desktop.ui_mode([]) == desktop.UI_NONE


class _StubKey:
    def __init__(self, pv):
        self.pv = pv

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _StubWinreg:
    """Only the Evergreen runtime key answers; every other lookup fails
    like a missing registry key would."""

    def __init__(self, pv):
        self.pv = pv

    def OpenKey(self, hive, subkey):
        if desktop._WEBVIEW2_CHANNELS[0] in subkey:
            return _StubKey(self.pv)
        raise OSError("missing key")

    def QueryValueEx(self, key, name):
        assert name == "pv"
        return (key.pv, None)


@pytest.mark.parametrize("pv,expected", [
    ("120.0.2210.61", True),      # a modern Evergreen runtime
    ("86.0.622.0", True),         # pywebview's exact floor
    ("85.0.564.34", False),       # below the floor - MSHTML territory
    ("0.0.0.0", False),           # registered but not actually installed
    ("unknown", False),           # unparseable
])
def test_webview2_detection_reads_the_edgeupdate_pv(pv, expected, monkeypatch):
    import sys as _sys
    import types

    class _Mod(types.ModuleType):
        pass

    mod = _Mod("winreg")
    stub = _StubWinreg(pv)
    mod.OpenKey = stub.OpenKey
    mod.QueryValueEx = stub.QueryValueEx
    mod.HKEY_CURRENT_USER = 2
    mod.HKEY_LOCAL_MACHINE = 1
    monkeypatch.setitem(_sys.modules, "winreg", mod)
    # the runtime short-circuits on non-Windows (native OS webview);
    # pin the platform so the registry stub is actually consulted
    monkeypatch.setattr(_sys, "platform", "win32")
    ok, detail = desktop.webview2_runtime_version()
    assert ok is expected
    if expected:
        assert pv in detail


# ---------------------------------------------------------------------------
# Second launch: surface the running instance
# ---------------------------------------------------------------------------

def _patch_ready_instance(monkeypatch, focus_result):
    monkeypatch.setattr(desktop, "read_runtime_port", lambda: 8901)
    monkeypatch.setattr(desktop, "_get",
                         lambda url, timeout=2.0: (True, 200, ""))
    monkeypatch.setattr(desktop, "read_runtime_ui", lambda: desktop.UI_WINDOW)
    monkeypatch.setattr(desktop, "_focus_existing_window",
                         lambda timeout_s=10.0: focus_result)


def test_second_launch_focuses_the_running_window(monkeypatch):
    _patch_ready_instance(monkeypatch, True)
    assert desktop.focus_existing() is True


def test_second_launch_quiet_surfaces_nothing(monkeypatch):
    _patch_ready_instance(monkeypatch, True)
    assert desktop.focus_existing(quiet=True) is True


# ---------------------------------------------------------------------------
# Second launch must NEVER exit silently ("nothing happens")
# ---------------------------------------------------------------------------

def _patch_instance(monkeypatch, ui, focus_result):
    monkeypatch.setattr(desktop, "read_runtime_port", lambda: 8902)
    monkeypatch.setattr(desktop, "_get",
                        lambda url, timeout=2.0: (True, 200, ""))
    monkeypatch.setattr(desktop, "read_runtime_ui", lambda: ui)
    monkeypatch.setattr(desktop, "_focus_existing_window",
                        lambda timeout_s=10.0: focus_result)
    dialogs: list[tuple[str, str]] = []
    monkeypatch.setattr(desktop, "show_error",
                        lambda title, msg: dialogs.append((title, msg)))
    return dialogs


def test_second_launch_focusing_succeeds_without_a_dialog(monkeypatch):
    dialogs = _patch_instance(monkeypatch, desktop.UI_WINDOW, True)
    assert desktop.focus_existing() is True
    assert dialogs == []


def test_second_launch_headless_instance_gets_an_honest_dialog(monkeypatch):
    """Regression (v1.0.3): a running HEADLESS instance (tests/CI) used
    to make the second launch exit quietly - the user's click appeared
    to do nothing. Now: an honest dialog naming the situation."""
    dialogs = _patch_instance(monkeypatch, desktop.UI_NONE, False)
    assert desktop.focus_existing() is True
    assert dialogs, "a second launch must not exit silently"
    title, msg = dialogs[0]
    assert title == "Telegram Query is already running"
    assert "headless" in msg and "8902" in msg


def test_second_launch_unfocusable_window_gets_an_honest_dialog(monkeypatch):
    """Regression (v1.0.3): a window instance whose window cannot be
    found (still starting past the 10s focus deadline, or hung) also
    exited quietly. Now: an honest dialog with recovery steps."""
    dialogs = _patch_instance(monkeypatch, desktop.UI_WINDOW, False)
    assert desktop.focus_existing() is True
    assert dialogs, "a second launch must not exit silently"
    title, msg = dialogs[0]
    assert title == "Telegram Query is already running"
    assert "window" in msg and "Task Manager" in msg


# ---------------------------------------------------------------------------
# Start-Menu shortcut: never target console-mode python.exe
# ---------------------------------------------------------------------------

def test_windowed_interpreter_prefers_pythonw(tmp_path):
    """Regression (v1.0.3): the dev shortcut targeted python.exe - a
    CONSOLE program - so every launch flashed a terminal that closed
    the moment the app exited or handed off, reading exactly like a
    crash. The shortcut must use pythonw.exe when it exists."""
    exe = tmp_path / "python.exe"
    exe.touch()
    windowed = tmp_path / "pythonw.exe"
    windowed.touch()
    assert desktop._windowed_interpreter(str(exe)) == str(windowed)


def test_windowed_interpreter_falls_back_to_the_exe(tmp_path):
    exe = tmp_path / "python.exe"
    exe.touch()
    assert desktop._windowed_interpreter(str(exe)) == str(exe)


def test_windowed_interpreter_frozen_exe_keeps_itself(tmp_path):
    # no pythonw next to the frozen exe -> the exe is the target
    exe = tmp_path / "TelegramQuery.exe"
    exe.touch()
    assert desktop._windowed_interpreter(str(exe)) == str(exe)


def test_shortcut_arguments_quote_paths_with_spaces(monkeypatch):
    """Regression (v1.0.3): the Start-Menu shortcut's Arguments field
    carried the script path UNQUOTED. Windows passes it verbatim on the
    command line, so with the repo under 'E:\\AI Projects\\...' (a path
    with a space) the interpreter received 'E:\\AI' as the script name
    and exited instantly - every click on the shortcut did NOTHING
    (no console under pythonw, a flashing error console under python).
    The argument must be one quoted token."""
    monkeypatch.setattr(desktop, "__file__",
                        r"E:\AI Projects\Telegram_quary\desktop.py")
    args = desktop._shortcut_arguments()
    assert args == '"E:\\AI Projects\\Telegram_quary\\desktop.py"'
    # and the quoted form is what the interpreter accepts as ONE token:
    # simulate the argv split the failure mode produced (space break)
    assert " " in args.strip('"')      # the path really has a space ...
    assert args.startswith('"') and args.endswith('"')   # ... and survives


def test_shortcut_arguments_real_launch_with_spaces(tmp_path):
    """End-to-end proof: launch the real interpreter exactly the way
    the shortcut does - a RAW command line (target + verbatim argument
    string) - against a script whose path contains spaces; it must RUN,
    not die on a split path."""
    import subprocess
    import sys as _sys
    folder = tmp_path / "AI Projects"          # the space that broke it
    folder.mkdir()
    marker = tmp_path / "marker.txt"
    script = folder / "write_marker.py"
    script.write_text(
        "import sys, pathlib\n"
        f"pathlib.Path(r'{marker}').write_text(sys.argv[1])\n",
        encoding="utf-8")
    args = f'"{script}"'                        # quoted, like the shortcut
    # the verbatim command line Explorer builds for the shortcut
    cmdline = f'"{_sys.executable}" {args} hello'
    r = subprocess.run(cmdline, capture_output=True, text=True,
                       timeout=30, shell=True)
    assert r.returncode == 0, r.stderr
    assert marker.read_text(encoding="utf-8") == "hello"


# ---------------------------------------------------------------------------
# System tray
# ---------------------------------------------------------------------------

def test_tray_icon_loads_from_ico():
    img = desktop._tray_icon_image()
    assert img is not None
    assert img.size[0] > 0 and img.size[1] > 0


def test_stop_tray_is_safe_when_not_started():
    old = desktop._TRAY
    desktop._TRAY = None
    try:
        desktop._stop_tray()
    finally:
        desktop._TRAY = old


# ---------------------------------------------------------------------------
# Initial window placement (small screens / high-DPI)
# ---------------------------------------------------------------------------

def test_fit_window_size_keeps_the_default_on_big_screens(monkeypatch):
    monkeypatch.setattr(desktop, "_primary_work_area", lambda: (1920, 1040))
    monkeypatch.setattr(desktop, "_primary_scale", lambda: 1.0)
    assert desktop.fit_window_size((1400, 900), (960, 600)) == (1400, 900)


def test_fit_window_size_clamps_to_a_1366x768_laptop(monkeypatch):
    # the classic budget-laptop resolution: the old fixed 1400x900 window
    # was larger than the whole screen on both axes
    monkeypatch.setattr(desktop, "_primary_work_area", lambda: (1366, 728))
    monkeypatch.setattr(desktop, "_primary_scale", lambda: 1.0)
    assert desktop.fit_window_size((1400, 900), (960, 600)) == (1366, 728)


def test_fit_window_size_clamps_at_150pct_scaling(monkeypatch):
    # 1920x1080 at 150%: 1400 logical width becomes 2100 PHYSICAL px -
    # wider than the monitor. Work area 1920x1032 -> 1280x688 logical.
    monkeypatch.setattr(desktop, "_primary_work_area", lambda: (1920, 1032))
    monkeypatch.setattr(desktop, "_primary_scale", lambda: 1.5)
    assert desktop.fit_window_size((1400, 900), (960, 600)) == (1280, 688)


def test_fit_window_size_tiny_screen_wins_over_the_minimum(monkeypatch):
    monkeypatch.setattr(desktop, "_primary_work_area", lambda: (1024, 560))
    monkeypatch.setattr(desktop, "_primary_scale", lambda: 1.0)
    assert desktop.fit_window_size((1400, 900), (960, 600)) == (1024, 560)


def test_fit_window_size_without_metrics_keeps_the_default(monkeypatch):
    # non-Windows / metrics unavailable: behaviour unchanged
    monkeypatch.setattr(desktop, "_primary_work_area", lambda: None)
    assert desktop.fit_window_size((1400, 900), (960, 600)) == (1400, 900)


# ---------------------------------------------------------------------------
# Startup failure reporting (the windowed exe has no console)
# ---------------------------------------------------------------------------

def test_startup_fails_fast_when_the_backend_thread_dies(
        data_dir, monkeypatch, reset_desktop_state, clean_root_logger):
    """Regression (v1.0.3): uvicorn exiting during startup (failed bind,
    startup crash) used to make the user wait the FULL startup timeout
    (60s by default) before the error dialog. The health poll must
    notice the dead server thread within one poll interval and report
    the honest reason."""
    import types
    fake_uvicorn = types.ModuleType("uvicorn")

    class _DeadServer:
        def __init__(self, cfg, **kw):
            pass

        def run(self):
            raise SystemExit("simulated bind failure")

    fake_uvicorn.Server = _DeadServer
    fake_uvicorn.Config = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    monkeypatch.setattr(desktop, "acquire_single_instance", lambda: True)
    monkeypatch.setattr(desktop, "ui_mode", lambda argv=None:
                        desktop.UI_NONE)
    monkeypatch.setattr(desktop, "focus_existing",
                        lambda quiet=False: True)
    monkeypatch.setenv("TGQ_STARTUP_TIMEOUT", "30")
    dialogs: list[tuple[str, str]] = []
    monkeypatch.setattr(desktop, "show_error",
                        lambda title, msg: dialogs.append((title, msg)))

    t0 = time.monotonic()
    rc = desktop.main([])
    elapsed = time.monotonic() - t0

    assert rc == 1
    assert elapsed < 10, (f"startup failure took {elapsed:.1f}s to "
                          "report - the dead-server fast path regressed")
    assert any("exited during startup" in m for _t, m in dialogs)


def test_unwritable_data_dir_shows_a_startup_dialog(
        data_dir, monkeypatch, reset_desktop_state, clean_root_logger):
    """Regression (v1.0.3): a failure BEFORE logging exists (data dir
    unwritable, disk full) killed the windowed exe SILENTLY - no
    console, no log file, nothing on screen. The user now gets the
    native error dialog plus a %TEMP% crash dump."""
    def _boom():
        raise OSError(5, "Access is denied")

    monkeypatch.setattr(desktop, "configure_logging", _boom)
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(data_dir))
    dialogs: list[tuple[str, str]] = []
    monkeypatch.setattr(desktop, "show_error",
                        lambda title, msg: dialogs.append((title, msg)))

    rc = desktop.main([])

    assert rc == 1
    assert dialogs, "an early startup failure must show a dialog"
    title, msg = dialogs[0]
    assert title == "Startup failed"
    assert str(config.DATA_DIR) in msg
    # operator evidence even without the log file
    dump = data_dir / "TelegramQuery-startup-error.log"
    assert dump.exists()
    assert "Access is denied" in dump.read_text(encoding="utf-8")


def test_late_startup_failure_is_reported_not_silent(
        data_dir, monkeypatch, reset_desktop_state, clean_root_logger):
    """Regression (v1.0.3): any unexpected exception AFTER logging is up
    (e.g. runtime.json unwritable) crashed the windowed exe silently.
    It must be logged and reported through the native dialog."""
    def _boom(path, ui):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(desktop, "acquire_single_instance", lambda: True)
    monkeypatch.setattr(desktop, "ui_mode", lambda argv=None:
                        desktop.UI_NONE)
    monkeypatch.setattr(desktop, "write_runtime_file", _boom)
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(data_dir))
    dialogs: list[tuple[str, str]] = []
    monkeypatch.setattr(desktop, "show_error",
                        lambda title, msg: dialogs.append((title, msg)))

    rc = desktop.main([])

    assert rc == 1
    assert dialogs, "an unexpected startup crash must show a dialog"
    title, msg = dialogs[0]
    assert title == "Startup failed"
    assert desktop.LOG_FILE in msg
