import re
import sqlite3
import threading
from pathlib import Path


DATABASE_NAME = "calf.sqlite3"
_write_lock = threading.Lock()


def table_name(server: str) -> str:
    if not isinstance(server, str) or not server.strip():
        raise ValueError("server must be a non-empty string")

    normalized = re.sub(r"[^0-9A-Za-z_]", "_", server.strip())
    return f"calf_{normalized}"


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _is_legacy_event_table(connection, metrics_table: str) -> bool:
    columns = {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({_quoted(metrics_table)})")
    }
    return bool(columns) and "event_json" in columns


def initialize_database(server: str, directory: Path | None = None) -> tuple[Path, str]:
    database_path = (directory or Path.cwd()) / DATABASE_NAME
    metrics_table = table_name(server)

    with sqlite3.connect(database_path, timeout=5) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        if _is_legacy_event_table(connection, metrics_table):
            legacy_table = f"{metrics_table}_events_legacy"
            connection.execute(
                f"ALTER TABLE {_quoted(metrics_table)} RENAME TO {_quoted(legacy_table)}"
            )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_quoted(metrics_table)} (
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                activity TEXT NOT NULL,
                requests INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                total_latency REAL NOT NULL DEFAULT 0,
                avg_latency REAL NOT NULL DEFAULT 0,
                last_latency REAL NOT NULL DEFAULT 0,
                last_status INTEGER NOT NULL DEFAULT 200,
                cpu_percent REAL NOT NULL DEFAULT 0,
                memory_mb REAL NOT NULL DEFAULT 0,
                gpu TEXT,
                last_called REAL NOT NULL,
                PRIMARY KEY (endpoint, method)
            )
            """
        )

    return database_path, metrics_table


def save_request_metrics(
    database_path: Path,
    metrics_table: str,
    event: dict,
    cpu_percent: float,
    memory_mb: float,
) -> None:
    if not event.get("method") or not event.get("path"):
        return

    latency = float(event.get("latency_ms", 0))
    status = int(event.get("status", 500))

    with _write_lock, sqlite3.connect(database_path, timeout=5) as connection:
        connection.execute(
            f"""
            INSERT INTO {_quoted(metrics_table)} (
                endpoint, method, activity, requests, failed, total_latency,
                avg_latency, last_latency, last_status, cpu_percent,
                memory_mb, gpu, last_called
            ) VALUES (?, ?, 'active', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(endpoint, method) DO UPDATE SET
                activity = 'active',
                requests = requests + 1,
                failed = failed + excluded.failed,
                avg_latency = (total_latency + excluded.last_latency) / (requests + 1),
                total_latency = total_latency + excluded.last_latency,
                last_latency = excluded.last_latency,
                last_status = excluded.last_status,
                cpu_percent = excluded.cpu_percent,
                memory_mb = excluded.memory_mb,
                gpu = excluded.gpu,
                last_called = excluded.last_called
            """,
            (
                event["path"],
                event.get("method"),
                int(status >= 400),
                latency,
                latency,
                latency,
                status,
                cpu_percent,
                memory_mb,
                event.get("cuda_visible_devices"),
                float(event.get("last_called", 0)),
            ),
        )


def load_metrics(database_path: Path, metrics_table: str) -> dict:
    if not database_path.exists():
        return {}

    with sqlite3.connect(database_path, timeout=5) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT endpoint, method, requests, failed, total_latency,
                   avg_latency, last_latency, last_status, cpu_percent,
                   memory_mb, gpu, last_called
            FROM {_quoted(metrics_table)}
            """
        ).fetchall()

    return {
        (row["method"], row["endpoint"]): {
            "method": row["method"],
            "path": row["endpoint"],
            "requests": row["requests"],
            "failed": row["failed"],
            "total_latency": row["total_latency"],
            "last_latency": row["last_latency"],
            "total_bytes": 0,
            "last_called": row["last_called"],
            "last_status": row["last_status"],
        }
        for row in rows
    }


def find_metrics_tables(database_path: Path) -> list[str]:
    if not database_path.exists():
        return []

    with sqlite3.connect(database_path, timeout=5) as connection:
        names = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'calf_%'"
        ).fetchall()

    return sorted(
        name for (name,) in names
        if not name.endswith("_events_legacy")
    )
