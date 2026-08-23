"""Start a four-worker server and send a short 100-request burst to it."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Result:
    name: str
    status: int
    latency_ms: float
    error: str | None = None


def call(base_url: str, index: int, timeout: float) -> Result:
    routes = (
        ("health", "GET", "/health", None),
        ("users", "GET", "/users", None),
        ("process", "POST", "/process", {"request": index}),
    )
    name, method, path, payload = routes[index % len(routes)]
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if body else {}
    request = Request(base_url + path, data=body, headers=headers, method=method)
    started = time.perf_counter()

    try:
        with urlopen(request, timeout=timeout) as response:
            response.read()
            status = response.status
        error = None
    except HTTPError as exc:
        status, error = exc.code, str(exc)
    except (URLError, TimeoutError, OSError) as exc:
        status, error = 0, str(exc)

    return Result(name, status, (time.perf_counter() - started) * 1000, error)


def wait_until_ready(base_url: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if call(base_url, 0, 1.0).status == 200:
            return
        time.sleep(0.1)
    raise RuntimeError(f"Server did not become ready at {base_url} within {timeout}s")


def verify_all_routes(base_url: str, timeout: float) -> None:
    expected = (
        ("/health", "GET", None, {"message": "healthy"}),
        ("/users", "GET", None, {"users": ["alice", "bob"]}),
        ("/process", "POST", {"check": True}, {"received": {"check": True}}),
    )
    for path, method, payload, wanted in expected:
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if body else {}
        request = Request(base_url + path, data=body, headers=headers, method=method)
        with urlopen(request, timeout=timeout) as response:
            actual = json.loads(response.read())
            if response.status != 200 or actual != wanted:
                raise AssertionError(f"{method} {path}: status={response.status}, body={actual}")
        print(f"PASS {method:4} {path}")


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * percent))
    return ordered[index]


def run_burst(base_url: str, requests: int, concurrency: int, timeout: float) -> int:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(call, base_url, index, timeout) for index in range(requests)]
        results = [future.result() for future in as_completed(futures)]
    elapsed = time.perf_counter() - started

    failures = [result for result in results if result.status != 200]
    latencies = [result.latency_ms for result in results]
    print("\nBurst results")
    print(f"  requests:    {len(results)}")
    print(f"  concurrency: {concurrency}")
    print(f"  elapsed:     {elapsed:.2f}s")
    print(f"  throughput:  {len(results) / elapsed:.1f} requests/s")
    print(f"  latency:     avg={sum(latencies) / len(latencies):.1f}ms "
          f"p95={percentile(latencies, .95):.1f}ms max={max(latencies):.1f}ms")
    print(f"  failures:    {len(failures)}")
    for failure in failures[:5]:
        print(f"    {failure.name}: status={failure.status} error={failure.error}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--external-server", action="store_true",
                        help="test an already-running server instead of starting Uvicorn")
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1 or args.workers < 1:
        parser.error("requests, concurrency, and workers must be positive")

    server = None
    try:
        if not args.external_server:
            port = args.url.rsplit(":", 1)[-1]
            command = [sys.executable, "-m", "uvicorn", "server.app:app", "--host",
                       "127.0.0.1", "--port", port, "--workers", str(args.workers)]
            print(f"Starting Uvicorn with {args.workers} workers...")
            server = subprocess.Popen(command, cwd=ROOT)
        wait_until_ready(args.url)
        verify_all_routes(args.url, args.timeout)
        return run_burst(args.url, args.requests, args.concurrency, args.timeout)
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    raise SystemExit(main())
