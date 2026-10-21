# 🐮 fastapi-calf

**A lightweight, real-time observability for FastAPI.**

`fastapi-calf` watches decorated API routes and presents request activity,
latency, throughput, failures, CPU, memory, and worker information in a compact
terminal UI. Monitoring is intentionally best-effort: if the dashboard is not
available, your API continues serving requests normally.

## Highlights

- ⚡ Live requests-per-second and latency sparklines
- 🧭 Per-route request, failure, status, and response-time statistics
- 🖥️ CPU and memory usage across multiple application workers
- 🎮 `CUDA_VISIBLE_DEVICES` reporting for GPU-aware deployments
- 🛡️ Short-timeout event delivery that never takes down the application

## Quick start

Install the runtime dependencies from the repository root:

```powershell
python -m pip install fastapi uvicorn rich psutil
```

Start the collector, web dashboard, and terminal UI on port `8765`:

```powershell
python -m fastapi_calf.daemon --port 8765
```

In another terminal, start the included example API with four workers:

```powershell
python -m uvicorn server.app:app --port 8000 --workers 4
```

Visit `http://127.0.0.1:8000/docs` to explore the API while the terminal
dashboard updates in real time.

Open `http://127.0.0.1:8000/calf` to redirect to the aggregated dashboard at
`http://127.0.0.1:8765/`. It refreshes once per second and combines route
traffic, failures, latency, event-loop stalls, and lifecycle timing from every
Uvicorn worker.

Run only the collector and web dashboard when the terminal view is not needed:

```powershell
python -m fastapi_calf.daemon --port 8765 --no-terminal
```

The web dashboard is enabled by default and can be moved or disabled:

```python
Calf.listen(app, port=8765, server="jobs_api", dashboard_path="/observability")
# Or: Calf.listen(..., dashboard=False)
```

Ignore health checks, metrics collectors, or other noisy paths with exact paths
or shell-style wildcards. Calf ignores `/favicon.ico` and its own dashboard
routes automatically.

```python
Calf.listen(
    app,
    port=8005,
    server="jobs_api",
    ignore_paths=("/health", "/ready", "/metrics", "/internal/*"),
)
```

Workers send best-effort HTTP events to the collector's `/api/events` endpoint.
The collector exposes aggregate JSON at `/api/stats`; both the web and terminal
views read the same in-memory process-wide aggregation.

## Instrumenting an API

Configure the monitor once, then decorate the routes you want to observe:

```python
from fastapi import FastAPI, Request
from fastapi_calf import Calf, lookout

app = FastAPI()
Calf.listen(app, port=8005, server="jobs_api")


@app.get("/health")
@lookout
def health(request: Request):
    return {"status": "healthy"}


@app.post("/jobs")
@lookout
async def create_job(request: Request):
    payload = await request.json()
    return {"accepted": True, "job": payload}
```

The `Request` parameter allows `@lookout` to capture the method, path, query
parameters, request size, status, and timing without changing the response.
Metrics are kept in memory by the live dashboard and reset when it stops.

### Event-loop blocking detection

Calf watches each worker's asyncio event loop and warns when it cannot run for
more than 100 ms. This catches blocking calls such as `time.sleep()`, synchronous
HTTP clients, filesystem operations, and CPU-heavy work used inside `async def`
endpoints. Overlapping requests are shown as affected rather than definitively
identified as the cause.

Tune or disable the detector when configuring the application:

```python
Calf.listen(
    app,
    port=8005,
    server="jobs_api",
    detect_blocking=True,
    block_threshold=100,
    block_check_interval=50,
)
```

Both values are milliseconds. `block_check_interval` controls how often the
watchdog asks the event loop to run. If it wakes at least `block_threshold`
milliseconds later than expected, Calf records a blocking event. A smaller
check interval detects stalls more precisely but wakes the watchdog more often.

The example server exposes `/block-event-loop` as an intentional blocking case
and `/cooperative-sleep` as its non-blocking comparison.

### Request lifecycle timing

Every HTTP event includes a `lifecycle` breakdown in milliseconds for request
body parsing, dependency injection and validation, endpoint execution, response
serialization, middleware/framework overhead, and background tasks. The live
dashboard shows the most recent breakdown for each route.

`middleware` is the residual request time after the directly measured phases;
it includes routing, middleware work, response construction, and response
transport. Streaming generator work is also included there because it occurs
after the endpoint has returned its iterator.

Try all lifecycle phases with the example endpoint:

```powershell
curl -X POST http://127.0.0.1:8000/lifecycle `
  -H "Content-Type: application/json" `
  -d '{"message":"hello"}'
```

## Tests and traffic simulation

Install the testing tools and run the correctness suite:

```powershell
python -m pip install -r requirements-test.txt
python -m pytest tests/test_api.py -q
```

The load runner starts four Uvicorn workers, verifies every sample endpoint,
and pushes **100 concurrent API calls** in a short burst:

```powershell
python -m tests.load_test
```

Customize a run with `--requests`, `--concurrency`, and `--workers`. See
[TESTING.md](TESTING.md) for additional examples.

## Project layout

```text
fastapi_calf/   monitoring library and terminal dashboard
server/         instrumented example FastAPI application
tests/          endpoint and concurrent load tests
```

> **Status:** This is an early-stage project intended for experimentations with ML pipelines and POCs.
