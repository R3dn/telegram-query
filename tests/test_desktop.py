"""Tests for desktop.py - the packaged-app lifecycle primitives.

Everything is tested against real sockets/servers on loopback; the
things that must never run in tests (native dialogs, the real mutex,
spawning the server) are monkeypatched.
"""
import json
import socket
import threading
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
                                                   monkeypatch):
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
