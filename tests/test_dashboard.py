import asyncio

from fastapi import FastAPI

from fastapi_calf.dashboard import DashboardStore, install_dashboard


def test_dashboard_store_aggregates_requests_and_blocks():
    store = DashboardStore("test")
    store.record({
        "method": "POST",
        "path": "/predict",
        "status": 200,
        "latency_ms": 25,
        "lifecycle": {"endpoint": 20, "total": 25},
    })
    store.record({
        "type": "loop_blocked",
        "blocked_ms": 150,
        "affected_requests": [{"method": "POST", "path": "/predict"}],
    })

    snapshot = store.snapshot()
    route = snapshot["routes"][0]
    assert snapshot["totals"] == {"requests": 1, "failures": 0, "blocks": 1}
    assert route["avg_latency_ms"] == 25
    assert route["blocks"] == 1
    assert route["worst_block_ms"] == 150


def test_dashboard_routes_are_hidden_from_openapi():
    app = FastAPI()
    store = DashboardStore("test")
    install_dashboard(app, store, "/calf")

    paths = {route.path: route for route in app.routes}
    assert paths["/calf"].include_in_schema is False
    assert paths["/calf/api/stats"].include_in_schema is False

    page = asyncio.run(paths["/calf"].endpoint())
    stats = asyncio.run(paths["/calf/api/stats"].endpoint())
    assert b"request monitor" in page.body
    assert b"color-scheme:light" in page.body
    assert b"Inter,ui-sans-serif" in page.body
    assert b'data-view="blocks"' in page.body
    assert b'data-view="table"' in page.body
    assert page.body.count(b"data-collapse aria-expanded") == 3
    assert stats["server"] == "test"
