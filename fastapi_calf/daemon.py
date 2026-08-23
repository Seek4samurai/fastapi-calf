import json
import time
import asyncio
import argparse

from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.console import Group

from .system import register_process, get_process_stats
from .history import cpu_history, latency_history, rps_history
from .metrics import record_request, get_rps, get_window_latency
from .sparkline import sparkline

workers = {
    # pid: {
    #     "requests": 0,
    #     "cuda_visible_devices": None,
    # }
}

stats = {}

start_time = time.time()

last_history_sample = 0


def process_event(event):
    pid = event.get("pid")

    if pid is not None:
        if pid not in workers:
            register_process(pid)

            workers[pid] = {
                "requests": 0,
                "cuda_visible_devices": event.get("cuda_visible_devices"),
            }

        # Update metadata if supplied again
        if "cuda_visible_devices" in event:
            workers[pid]["cuda_visible_devices"] = event["cuda_visible_devices"]

    # This was only a process/system event
    if "method" not in event or "path" not in event:
        return

    if pid is not None:
        workers[pid]["requests"] += 1

    key = (event["method"], event["path"])

    record_request(event["latency_ms"])

    if key not in stats:
        stats[key] = {
            "method": event["method"],
            "path": event["path"],
            "requests": 0,
            "failed": 0,
            "total_latency": 0,
            "last_latency": 0,
            "total_bytes": 0,
            "last_called": 0,
            "last_status": 200,
        }

    item = stats[key]

    item["requests"] += 1
    item["total_latency"] += event["latency_ms"]
    item["last_latency"] = event["latency_ms"]
    item["total_bytes"] += event["request_size"]
    item["last_called"] = time.time()
    item["last_status"] = event["status"]

    # Count failed requests
    if event["status"] >= 400:
        item["failed"] += 1


def sample_history(process_stats):
    global last_history_sample

    now = time.time()

    if now - last_history_sample < 1:
        return

    if process_stats:
        cpu_history.append(process_stats["cpu"])

    latency_history.append(get_window_latency())

    rps_history.append(get_rps())

    last_history_sample = now


def latest(values, default=0):
    return values[-1] if values else default


def build_history_panel():
    return Group(
        Text(
            f"CPU       "
            f"{latest(cpu_history):5.1f}%  "
            f"{sparkline(cpu_history, 0, 100)}"
        ),
        Text(
            f"Latency   "
            f"{latest(latency_history):5.1f}ms "
            f"{sparkline(latency_history)}"
        ),
        Text(
            f"RPS       "
            f"{latest(rps_history):5.1f}   "
            f"{sparkline(rps_history)}"
        ),
    )


def get_total_process_stats():
    total_cpu = 0
    total_ram = 0
    count = 0

    for pid in workers:
        process_stats = get_process_stats(pid)

        if process_stats is None:
            continue

        total_cpu += process_stats["cpu"]
        total_ram += process_stats["ram_mb"]
        count += 1

    if count == 0:
        return None

    return {
        "cpu": total_cpu,
        "ram_mb": total_ram,
    }


def create_table():
    table = Table(expand=True)

    table.add_column("Endpoint")
    table.add_column("Method")
    table.add_column("Activity")
    table.add_column("Requests", justify="right")
    table.add_column("Failed", justify="right")
    table.add_column("Avg latency", justify="right")
    table.add_column("Last", justify="right")
    table.add_column("Status", justify="right")

    now = time.time()

    for item in stats.values():
        avg_latency = (item["total_latency"] / item["requests"] if item["requests"] > 0 else 0)

        active = ("● ● ●" if now - item["last_called"] < 0.5 else "")

        failed_display = (f"[red]{item['failed']}[/red]" if item["failed"] > 0 else "0")

        style = ("bold red" if item["last_status"] >= 400 else None)

        table.add_row(
            item["path"],
            item["method"],
            active,
            str(item["requests"]),
            failed_display,
            f"{avg_latency:.2f} ms",
            f"{item['last_latency']:.2f} ms",
            str(item["last_status"]),
            style=style,
        )

    process_stats = get_total_process_stats()

    if process_stats:
        system_text = (
            f"CPU {process_stats['cpu']:.0f}%"
            f"    Memory {process_stats['ram_mb']:.0f} MB"
            f"    Workers {len(workers)}"
        )
    else:
        system_text = "CPU --    Memory --    Workers --"

    sample_history(process_stats)

    workers_table = create_workers_table()

    return Group(
        Align.center(Text("fastapi-calf", style="bold")),
        Align.center(Text(system_text)),
        Text(""),
        build_history_panel(),
        Text(""),
        workers_table,
        Text(""),
        table,
    )


def create_workers_table():
    table = Table(title="Workers", expand=True)

    table.add_column("PID")
    table.add_column("CPU", justify="right")
    table.add_column("Memory", justify="right")
    table.add_column("Requests", justify="right")
    table.add_column("GPU", justify="right")

    dead_workers = []

    for pid, worker in workers.items():
        process_stats = get_process_stats(pid)

        if process_stats is None:
            dead_workers.append(pid)
            continue

        gpu = worker["cuda_visible_devices"]

        table.add_row(
            str(pid),
            f"{process_stats['cpu']:.1f}%",
            f"{process_stats['ram_mb']:.1f} MB",
            str(worker["requests"]),
            "none" if gpu is None else str(gpu),
        )

    for pid in dead_workers:
        workers.pop(pid, None)

    return table


async def handle_client(reader, writer):
    data = await reader.readline()

    if data:
        try:
            event = json.loads(data)
            process_event(event)
        except json.JSONDecodeError:
            pass

    writer.close()
    await writer.wait_closed()


async def run_server(port: int):
    server = await asyncio.start_server(handle_client, "127.0.0.1", port)
    async with server:
        await server.serve_forever()


async def run_ui():
    with Live(create_table(), refresh_per_second=10, screen=True) as live:
        while True:
            live.update(create_table())
            await asyncio.sleep(0.1)


async def main(port: int):
    await asyncio.gather(run_server(port), run_ui())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-p", "--port", type=int, default=8765, help="Port for fastapi-calf")

    args = parser.parse_args()

    asyncio.run(main(args.port))
