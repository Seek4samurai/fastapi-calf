import asyncio

from fastapi import FastAPI

from fastapi_calf.dashboard import (
    DashboardStore,
    install_dashboard,
    install_dashboard_redirect,
)


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
    assert snapshot["totals"] == {
        "requests": 1,
        "failures": 0,
        "blocks": 1,
        "workers": 0,
    }
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


def test_dashboard_aggregates_multiple_workers():
    store = DashboardStore("collector")
    for pid in (101, 202):
        store.record({"pid": pid, "_calf_server": "api"})
        store.record({
            "pid": pid,
            "_calf_server": "api",
            "method": "GET",
            "path": "/users",
            "status": 200,
            "latency_ms": 10,
        })

    snapshot = store.snapshot()
    assert snapshot["server"] == "api"
    assert snapshot["totals"]["workers"] == 2
    assert snapshot["totals"]["requests"] == 2
    assert snapshot["routes"][0]["requests"] == 2
    assert {worker["pid"] for worker in snapshot["workers"]} == {101, 202}


def test_dashboard_can_be_installed_at_collector_root():
    app = FastAPI()
    install_dashboard(app, DashboardStore("collector"), "/")
    paths = {route.path for route in app.routes}
    assert "/" in paths
    assert "/api/stats" in paths


def test_application_dashboard_redirects_to_collector():
    app = FastAPI()
    install_dashboard_redirect(app, "/calf", "http://127.0.0.1:8765/")
    route = next(route for route in app.routes if route.path == "/calf")
    response = asyncio.run(route.endpoint())
    assert response.status_code == 307
    assert response.headers["location"] == "http://127.0.0.1:8765/"
