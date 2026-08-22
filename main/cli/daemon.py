import asyncio
import json
import time

from rich.live import Live
from rich.table import Table


stats = {}

start_time = time.time()


def process_event(event):
    key = (event["method"], event["path"])

    if key not in stats:
        stats[key] = {
            "method": event["method"],
            "path": event["path"],
            "requests": 0,
            "total_latency": 0,
            "last_latency": 0,
            "total_bytes": 0,
            "last_called": 0,
        }

    item = stats[key]

    item["requests"] += 1

    item["total_latency"] += event["latency_ms"]

    item["last_latency"] = event["latency_ms"]

    item["total_bytes"] += event["request_size"]

    item["last_called"] = time.time()


def create_table():
    table = Table(title="MonitorDev", expand=True)

    table.add_column("Endpoint")
    table.add_column("Method")
    table.add_column("Activity")
    table.add_column("Requests", justify="right")
    table.add_column("Avg latency", justify="right")
    table.add_column("Last", justify="right")
    table.add_column("Req/sec", justify="right")
    table.add_column("Bytes", justify="right")

    uptime = max(time.time() - start_time, 0.001)

    now = time.time()

    for item in stats.values():
        avg_latency = item["total_latency"] / item["requests"]

        requests_per_second = item["requests"] / uptime

        # Show activity symbol for 0.5 sec
        active = ("●" if now - item["last_called"] < 0.5 else "")

        table.add_row(
            item["path"],
            item["method"],
            active,
            str(item["requests"]),
            f"{avg_latency:.2f} ms",
            f'{item["last_latency"]:.2f} ms',
            f"{requests_per_second:.2f}",
            str(item["total_bytes"]),
        )

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


async def run_server():
    server = await asyncio.start_server(handle_client, "127.0.0.1", 8765)
    async with server:
        await server.serve_forever()


async def run_ui():
    with Live(create_table(), refresh_per_second=10, screen=True) as live:
        while True:
            live.update(create_table())
            await asyncio.sleep(0.1)


async def main():
    await asyncio.gather(run_server(), run_ui())


if __name__ == "__main__":
    asyncio.run(main())
