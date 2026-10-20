import asyncio

from fastapi_calf import daemon
from fastapi_calf.lifecycle import CalfLifecycleMiddleware, LifecycleTrace


def test_lifecycle_trace_measures_phases_and_residual():
    async def scenario():
        trace = LifecycleTrace()
        await trace.measure("dependencies", lambda: asyncio.sleep(0.02))
        await trace.measure("endpoint", lambda: asyncio.sleep(0.01))
        return trace.finish()

    lifecycle = asyncio.run(scenario())

    assert lifecycle["dependencies"] >= 15
    assert lifecycle["endpoint"] >= 5
    assert lifecycle["middleware"] >= 0
    assert lifecycle["total"] >= lifecycle["dependencies"] + lifecycle["endpoint"]


def test_nested_phase_time_is_not_counted_twice():
    async def scenario():
        trace = LifecycleTrace()

        async def endpoint_work():
            await asyncio.sleep(0.01)
            await trace.measure("parsing", lambda: asyncio.sleep(0.02))
            await asyncio.sleep(0.01)

        await trace.measure("endpoint", endpoint_work)
        return trace.finish()

    lifecycle = asyncio.run(scenario())

    assert lifecycle["parsing"] >= 15
    assert lifecycle["endpoint"] >= 15
    measured = sum(
        lifecycle[phase]
        for phase in (
            "parsing",
            "dependencies",
            "endpoint",
            "serialization",
            "middleware",
            "background",
        )
    )
    assert abs(measured - lifecycle["total"]) < 1


def test_daemon_stores_and_renders_lifecycle(monkeypatch):
    daemon.workers.clear()
    daemon.stats.clear()
    daemon.blocking_alerts.clear()
    monkeypatch.setattr(daemon, "register_process", lambda pid: None)
    lifecycle = {
        "parsing": 1.0,
        "dependencies": 2.0,
        "endpoint": 3.0,
        "serialization": 4.0,
        "middleware": 5.0,
        "background": 6.0,
        "total": 21.0,
    }

    daemon.process_event({
        "pid": 123,
        "method": "POST",
        "path": "/lifecycle",
        "status": 200,
        "latency_ms": 21.0,
        "lifecycle": lifecycle,
    })

    assert daemon.stats[("POST", "/lifecycle")]["lifecycle"] == lifecycle
    table = daemon.create_lifecycle_table()
    assert table.row_count == 1


def test_lifecycle_middleware_ignores_exact_and_wildcard_paths():
    middleware = CalfLifecycleMiddleware(
        app=None,
        emit=None,
        dashboard_path="/calf",
        ignore_paths=("/favicon.ico", "/health", "/internal/*"),
    )

    assert middleware._should_ignore("/calf")
    assert middleware._should_ignore("/calf/api/stats")
    assert middleware._should_ignore("/favicon.ico")
    assert middleware._should_ignore("/health")
    assert middleware._should_ignore("/internal/jobs/42")
    assert not middleware._should_ignore("/users/42")
