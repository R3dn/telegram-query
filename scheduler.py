"""Auto-sync scheduler (v0.4).

Synchronizes tracked groups automatically at a configurable interval.

Design:
  - ALL state lives in the ``app_settings`` table (DB-persisted), so the
    schedule survives application restarts. The loop thread is stateless
    between ticks and re-reads state every ~30s - Settings changes apply
    without restarting the app.
  - Syncs go through jobs.JOBS, the same serialized job runner as the
    manual button: one job at a time, deduped - a scheduled sync can never
    overlap a running one.
  - When the app was closed past a due time, the first tick fires a single
    catch-up sync immediately, then resumes the normal cadence.
  - The scheduler only ever starts ``sync`` jobs; resume/checkpoint/flood
    handling is the sync pipeline's own job (backfill_floor, FloodWait).

app_settings keys:
  scheduler_enabled      '1' | '0'           (default '1' - on, conservative)
  scheduler_interval_min int as str          (default 360 = 6 hours)
  scheduler_next_due    ISO 8601 UTC datetime
  scheduler_last_success ISO 8601 UTC datetime (last sync that finished ok)
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import config
import db
import jobs

__all__ = ["get_state", "apply_config", "should_fire", "run_loop", "stop",
           "MIN_INTERVAL_MIN", "MAX_INTERVAL_MIN", "DEFAULT_INTERVAL_MIN",
           "DEFAULT_ENABLED"]

MIN_INTERVAL_MIN = 15
MAX_INTERVAL_MIN = 7 * 24 * 60   # one week
DEFAULT_INTERVAL_MIN = 360       # 6 hours - conservative default
DEFAULT_ENABLED = True

_STOP = threading.Event()
_seen_done: float | None = None   # last JOBS.last_done timestamp recorded


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def get_state(conn) -> dict:
    """Current scheduler state (with defaults for missing keys)."""
    enabled = db.get_setting(conn, "scheduler_enabled",
                             "1" if DEFAULT_ENABLED else "0")
    try:
        interval = int(db.get_setting(conn, "scheduler_interval_min",
                                     str(DEFAULT_INTERVAL_MIN)))
    except (TypeError, ValueError):
        interval = DEFAULT_INTERVAL_MIN
    interval = max(MIN_INTERVAL_MIN, min(MAX_INTERVAL_MIN, interval))
    return {
        "enabled": enabled == "1",
        "interval_min": interval,
        "next_due": db.get_setting(conn, "scheduler_next_due"),
        "last_success": db.get_setting(conn, "scheduler_last_success"),
    }


def apply_config(conn, enabled: bool | None = None,
                 interval_min: int | None = None) -> dict:
    """Validate + persist configuration; recompute the next due time."""
    st = get_state(conn)
    new_enabled = st["enabled"] if enabled is None else bool(enabled)
    new_interval = st["interval_min"]
    if interval_min is not None:
        try:
            new_interval = int(interval_min)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"interval must be {MIN_INTERVAL_MIN}-{MAX_INTERVAL_MIN} minutes") from e
        if not (MIN_INTERVAL_MIN <= new_interval <= MAX_INTERVAL_MIN):
            raise ValueError(
                f"interval must be {MIN_INTERVAL_MIN}-{MAX_INTERVAL_MIN} minutes")
    db.set_setting(conn, "scheduler_enabled", "1" if new_enabled else "0")
    db.set_setting(conn, "scheduler_interval_min", str(new_interval))
    # schedule from now (or, when being disabled, clear the due time)
    now = _now()
    if new_enabled:
        db.set_setting(conn, "scheduler_next_due",
                       (now + timedelta(minutes=new_interval)).isoformat())
    else:
        conn.execute("DELETE FROM app_settings WHERE key='scheduler_next_due'")
    conn.commit()
    return get_state(conn)


def should_fire(state: dict, now: datetime) -> bool:
    """Pure decision: is a scheduled sync due right now?"""
    if not state["enabled"] or not config.settings.telegram_configured:
        return False
    due = state["next_due"]
    if not due:
        return False  # first tick initializes the schedule (see run_loop)
    try:
        due_dt = datetime.fromisoformat(due)
    except ValueError:
        return False
    if due_dt.tzinfo is None:
        due_dt = due_dt.replace(tzinfo=timezone.utc)
    return now >= due_dt


def _tick(conn=None) -> None:
    """One scheduler iteration. Kept small for testability.

    ``conn``: existing connection (tests); None opens the default DB."""
    global _seen_done
    own = conn is None
    conn = db.get_db() if own else conn
    try:
        now = _now()
        state = get_state(conn)
        if state["enabled"] and not state["next_due"]:
            # fresh install / first enable: first due is one full interval
            # away (never an immediate surprise sync)
            db.set_setting(conn, "scheduler_next_due",
                           (now + timedelta(minutes=state["interval_min"])).isoformat())
            conn.commit()
            state = get_state(conn)
        if should_fire(state, now):
            days = config.settings.sync_days
            started = jobs.JOBS.start(
                "sync", lambda: jobs.run_sync_job(days=days))
            if started:
                # advance the schedule; if the runner deduped us (a sync is
                # already running/queued), leave the due time - retry next tick
                db.set_setting(conn, "scheduler_next_due",
                               (now + timedelta(minutes=state["interval_min"])).isoformat())
                conn.commit()
                print(f"[scheduler] auto-sync started "
                      f"(next in {state['interval_min']} min)")
        # record successful syncs (manual or scheduled) for the UI
        with jobs.JOBS.lock:
            last_done = jobs.JOBS.last_done
        if last_done and last_done.get("name") == "sync" and last_done.get("ok") \
                and last_done.get("finished_at") != _seen_done:
            _seen_done = last_done["finished_at"]
            db.set_setting(conn, "scheduler_last_success", now.isoformat())
            conn.commit()
        # v0.6: digest schedules ride the same 30s loop (cheap when idle)
        for hook in jobs.TICK_HOOKS:
            try:
                hook(conn)
            except Exception as e:  # noqa: BLE001 - a hook never kills the loop
                print(f"[scheduler] tick hook failed: {e}")
    finally:
        if own:
            conn.close()


def run_loop(interval_s: float = 30.0):
    """Thread body: tick, sleep, repeat (daemon thread)."""
    while not _STOP.is_set():
        try:
            _tick()
        except Exception as e:  # noqa: BLE001 - a scheduler tick must never die
            print(f"[scheduler] tick failed: {e}")
        _STOP.wait(interval_s)


def stop():
    """Ask the loop to exit (tests)."""
    _STOP.set()
