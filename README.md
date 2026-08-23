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

Start the monitoring dashboard on port `8005`:

```powershell
python -m fastapi_calf.daemon --port 8005
```

In another terminal, start the included example API with four workers:

```powershell
python -m uvicorn server.app:app --port 8000 --workers 4
```

Visit `http://127.0.0.1:8000/docs` to explore the API while the terminal
dashboard updates in real time.

## Instrumenting an API

Configure the monitor once, then decorate the routes you want to observe:

```python
from fastapi import FastAPI, Request
from fastapi_calf import Calf, lookout

app = FastAPI()
Calf.listen(port=8005)


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

