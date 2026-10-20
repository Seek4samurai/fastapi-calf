import asyncio
import time

from fastapi_calf.blocking import BlockingDetector
from fastapi_calf import daemon


def test_detector_reports_blocking_work_and_route():
    events = []

    async def capture(event):
        events.append(event)

    async def scenario():
        detector = BlockingDetector(capture, interval=0.01, threshold=0.04)
        detector.start()
        request_id = detector.register("GET", "/blocked")

        # Let the watchdog establish its next expected wake-up first.
        await asyncio.sleep(0.02)
        time.sleep(0.10)
        detector.unregister(request_id)
        await asyncio.sleep(0.03)
        await detector.stop()

    asyncio.run(scenario())

    assert events
    assert events[0]["type"] == "loop_blocked"
    assert events[0]["blocked_ms"] >= 40
    assert any(
        request["path"] == "/blocked"
        for request in events[0]["affected_requests"]
    )


def test_detector_ignores_cooperative_async_sleep():
    events = []

    async def capture(event):
        events.append(event)

    async def scenario():
        detector = BlockingDetector(capture, interval=0.01, threshold=0.05)
        detector.start()
        request_id = detector.register("GET", "/cooperative")
        await asyncio.sleep(0.10)
        detector.unregister(request_id)
        await detector.stop()

    asyncio.run(scenario())

    assert events == []


def test_daemon_aggregates_blocking_events_by_worker_and_route(monkeypatch):
    daemon.workers.clear()
    daemon.stats.clear()
    daemon.blocking_alerts.clear()
    monkeypatch.setattr(daemon, "register_process", lambda pid: None)

    daemon.process_event({
        "type": "loop_blocked",
        "pid": 123,
        "blocked_ms": 275.5,
        "affected_requests": [
            {"method": "GET", "path": "/blocked"},
        ],
    })

    assert daemon.workers[123]["blocks"] == 1
    assert daemon.workers[123]["worst_block_ms"] == 275.5
    assert daemon.stats[("GET", "/blocked")]["blocks"] == 1
    assert daemon.stats[("GET", "/blocked")]["worst_block_ms"] == 275.5
