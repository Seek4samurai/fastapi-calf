import json
import time
import asyncio
import argparse

from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.console import Group

from .system import set_process, get_process_stats


stats = {}

start_time = time.time()

current_pid = None

cuda_visible_devices = None

def process_event(event):
    global current_pid
    global cuda_visible_devices

    pid = event.get("pid")

    if pid is not None and pid != current_pid:
        set_process(pid)
        current_pid = pid
        cuda_visible_devices = event.get("cuda_visible_devices")
        return

    key = (event["method"], event["path"])

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

    process_stats = get_process_stats()

    global cuda_visible_devices

    if process_stats:
        system_text = (
            f"CPU {process_stats['cpu']:.1f}%"
            f"    Memory {process_stats['ram_mb']:.1f} MB"
            f"    GPU {"none" if cuda_visible_devices is None else cuda_visible_devices}"
        )
    else:
        system_text = "CPU --    Memory --    GPU --"

    return Group(
        Align.center(Text("fastapi-calf", style="bold")),
        Align.center(Text(system_text)),
        table,
    )


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
