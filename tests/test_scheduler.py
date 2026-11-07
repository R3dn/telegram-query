"""Auto-sync scheduler tests: state, validation, decision logic, API."""
from datetime import datetime, timedelta, timezone

import pytest

import config
import db
import scheduler


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def test_defaults_and_get_state(conn):
    st = scheduler.get_state(conn)
    assert st["enabled"] is True
    assert st["interval_min"] == scheduler.DEFAULT_INTERVAL_MIN
    assert st["next_due"] is None
    assert st["last_success"] is None


def test_apply_config_validates_interval(conn):
    with pytest.raises(ValueError):
        scheduler.apply_config(conn, interval_min=5)
    with pytest.raises(ValueError):
        scheduler.apply_config(conn, interval_min=100000)
    st = scheduler.apply_config(conn, interval_min=30)
    assert st["interval_min"] == 30
    assert st["next_due"]  # a schedule exists immediately


def test_disable_clears_next_due(conn):
    scheduler.apply_config(conn, enabled=True, interval_min=30)
    st = scheduler.apply_config(conn, enabled=False)
    assert st["enabled"] is False
    assert st["next_due"] is None


def test_should_fire_logic(conn):
    now = now_utc()
    st = scheduler.apply_config(conn, enabled=True, interval_min=60)
    # schedule starts one full interval out - never an immediate surprise
    assert scheduler.should_fire(st, now) is False
    # past the due time -> fires
    late = now + timedelta(minutes=61)
    assert scheduler.should_fire(st, late) is True
    # disabled -> never
    st["enabled"] = False
    assert scheduler.should_fire(st, late) is False
    # catch-up: app was closed over the due time -> fires on first tick
    st["enabled"] = True
    st["next_due"] = (now - timedelta(hours=2)).isoformat()
    assert scheduler.should_fire(st, now) is True


def test_should_fire_requires_telegram(conn, monkeypatch):
    monkeypatch.setattr(config.settings, "tg_api_id", "")
    monkeypatch.setattr(config.settings, "tg_api_hash", "")
    st = scheduler.get_state(conn)
    st["next_due"] = (now_utc() - timedelta(minutes=5)).isoformat()
    assert scheduler.should_fire(st, now_utc()) is False


def test_tick_starts_sync_and_advances_schedule(conn, monkeypatch):
    started = []
    monkeypatch.setattr(scheduler.jobs.JOBS, "start",
                        lambda name, func, front=False: started.append(name) or True)
    # force the schedule to be due right now
    past = (now_utc() - timedelta(minutes=1)).isoformat()
    db.set_setting(conn, "scheduler_enabled", "1")
    db.set_setting(conn, "scheduler_interval_min", "90")
    db.set_setting(conn, "scheduler_next_due", past)
    conn.commit()

    scheduler._tick(conn)
    assert started == ["sync"]
    st = scheduler.get_state(conn)
    assert st["next_due"], "schedule must advance after firing"
    due = datetime.fromisoformat(st["next_due"])
    assert due > now_utc() - timedelta(minutes=1)


def test_tick_deduped_sync_keeps_due_time(conn, monkeypatch):
    """If a sync is already running/queued the runner dedupes: keep the due
    time so the next tick retries instead of skipping a whole interval."""
    monkeypatch.setattr(scheduler.jobs.JOBS, "start", lambda *a, **k: False)
    past = (now_utc() - timedelta(minutes=1)).isoformat()
    db.set_setting(conn, "scheduler_enabled", "1")
    db.set_setting(conn, "scheduler_next_due", past)
    conn.commit()
    scheduler._tick(conn)
    st = scheduler.get_state(conn)
    assert st["next_due"] == past, "due time must not move on dedupe"


def test_tick_records_successful_syncs(conn, monkeypatch):
    monkeypatch.setattr(scheduler.jobs.JOBS, "start", lambda *a, **k: False)
    scheduler.jobs.JOBS.last_done = {"name": "sync", "ok": True,
                                     "finished_at": 123.456}
    scheduler._tick(conn)
    st = scheduler.get_state(conn)
    assert st["last_success"], "a finished sync must be recorded"
    scheduler.jobs.JOBS.last_done = None


def test_scheduler_api_roundtrip(api_client):
    r = api_client.get("/api/scheduler")
    assert r.status_code == 200
    assert r.json()["enabled"] is True

    r = api_client.post("/api/scheduler", json={"interval_min": 5})
    assert r.status_code == 400
    assert "15" in r.json()["error"]

    r = api_client.post("/api/scheduler",
                        json={"enabled": False, "interval_min": 45})
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False and body["interval_min"] == 45

    r = api_client.post("/api/scheduler", json={"enabled": True})
    assert r.json()["enabled"] is True
    assert api_client.get("/api/scheduler").json()["next_due"]
