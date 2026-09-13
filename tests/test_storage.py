import sqlite3

import pytest

from fastapi_calf.storage import initialize_database, load_metrics, save_request_metrics, table_name


def test_endpoint_metrics_are_aggregated_and_reused(tmp_path):
    database_path, event_table = initialize_database("orders-api", tmp_path)
    save_request_metrics(database_path, event_table, {
        "method": "GET",
        "path": "/health",
        "status": 200,
        "latency_ms": 1.0,
        "last_called": 10.0,
    }, cpu_percent=12.5, memory_mb=64.0)

    same_path, same_table = initialize_database("orders-api", tmp_path)
    save_request_metrics(same_path, same_table, {
        "method": "GET",
        "path": "/health",
        "status": 500,
        "latency_ms": 3.0,
        "last_called": 20.0,
        "cuda_visible_devices": "0",
    }, cpu_percent=25.0, memory_mb=70.0)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            f'''SELECT endpoint, method, requests, failed, avg_latency,
                       last_latency, last_status, cpu_percent, memory_mb, gpu
                FROM "{event_table}"'''
        ).fetchone()

    assert database_path == tmp_path / "calf.sqlite3"
    assert event_table == "calf_orders_api"
    assert row == ("/health", "GET", 2, 1, 2.0, 3.0, 500, 25.0, 70.0, "0")

    restored = load_metrics(database_path, event_table)
    assert restored[("GET", "/health")]["requests"] == 2
    assert restored[("GET", "/health")]["failed"] == 1
    assert restored[("GET", "/health")]["total_latency"] == 4.0


def test_process_events_are_not_stored(tmp_path):
    database_path, event_table = initialize_database("api", tmp_path)
    save_request_metrics(database_path, event_table, {"pid": 123}, 1.0, 2.0)

    with sqlite3.connect(database_path) as connection:
        count = connection.execute(
            f'SELECT COUNT(*) FROM "{event_table}"'
        ).fetchone()[0]

    assert count == 0


def test_server_name_must_not_be_empty():
    with pytest.raises(ValueError, match="non-empty"):
        table_name("  ")
