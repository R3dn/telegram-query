"""Job runner tests: queue order, dedupe, priority, cancel, completion."""
import threading
import time

import jobs


def test_runs_immediately_when_idle():
    jobs.JOBS.queue.clear()
    jobs.JOBS.running = False
    done = threading.Event()
    assert jobs.JOBS.start("sync", lambda: done.set()) is True
    assert done.wait(2)


def test_queue_runs_in_order():
    jobs.JOBS.queue.clear()
    jobs.JOBS.running = False
    order = []
    started = threading.Event()

    def blocker():
        started.set()
        time.sleep(0.15)

    assert jobs.JOBS.start("auth", blocker) is True          # runs first
    assert jobs.JOBS.start("track", lambda: order.append(1)) is True
    assert jobs.JOBS.start("track", lambda: order.append(2)) is True  # tracks queue
    started.wait(2)
    # wait for the queue to drain
    for _ in range(100):
        if not jobs.JOBS.running and not jobs.JOBS.queue:
            break
        time.sleep(0.02)
    assert order == [1, 2]
    assert jobs.JOBS.last_done is not None
    assert jobs.JOBS.last_done["ok"] is True


def test_dedupe_sync_and_dialogs():
    jobs.JOBS.queue.clear()
    jobs.JOBS.running = False
    jobs.JOBS.start("sync", lambda: None)
    # second sync while first is queued/running is rejected
    assert jobs.JOBS.start("sync", lambda: None) is False
    assert jobs.JOBS.start("dialogs", lambda: None) is True
    assert jobs.JOBS.start("dialogs", lambda: None) is False
    # drain
    for _ in range(200):
        if not jobs.JOBS.running and not jobs.JOBS.queue:
            break
        time.sleep(0.01)


def test_front_priority():
    jobs.JOBS.queue.clear()
    jobs.JOBS.running = False
    names = []
    started = threading.Event()

    def blocker():
        started.set()
        time.sleep(0.1)

    jobs.JOBS.start("auth", blocker)
    jobs.JOBS.start("track", lambda: names.append("track"))
    jobs.JOBS.start("dialogs", lambda: names.append("dialogs"), front=True)
    started.wait(2)
    for _ in range(100):
        if not jobs.JOBS.running and not jobs.JOBS.queue:
            break
        time.sleep(0.02)
    assert names == ["dialogs", "track"]


def test_failed_job_reports_not_ok():
    jobs.JOBS.queue.clear()
    jobs.JOBS.running = False

    def boom():
        raise RuntimeError("kaboom")

    jobs.JOBS.start("sync", boom)
    for _ in range(100):
        if jobs.JOBS.last_done and not jobs.JOBS.running:
            break
        time.sleep(0.02)
    assert jobs.JOBS.last_done["ok"] is False
    assert "kaboom" in jobs.JOBS.log
