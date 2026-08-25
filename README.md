# 🐮 fastapi-calf 🐮

`fastapi-calf` is a lightweight terminal monitor for FastAPI applications. It
shows live route activity, request counts, failures, latency, requests per
second, CPU and memory use, and worker process information.

Monitoring is best-effort. The application sends small events to the dashboard
over TCP with a short timeout; an unavailable dashboard does not stop requests
from being served.

## Requirements

- Python 3.10 or newer
- `rich` and `psutil` for the monitoring package
- FastAPI and an ASGI server such as Uvicorn in the application being monitored

FastAPI is intentionally not installed as a dependency of `fastapi-calf`. This
keeps the monitoring package small and allows the application to manage its own
FastAPI version.

## Installation

Install the package from the repository:

```bash
python -m pip install .
```

For local development, use an editable install:

```bash
python -m pip install -e .
```

The application environment must provide FastAPI and an ASGI server:

```bash
python -m pip install fastapi uvicorn
```

Installing the package creates the `calf` command.

## Quick start

### 1. Add the middleware

Create or update the FastAPI application:

```python
from fastapi import FastAPI
from fastapi_calf import Calf

app = FastAPI()

# The dashboard started in the next step listens on this port.
Calf.listen(app, host="127.0.0.1", port=8765)


@app.get("/health")
def health():
    return {"status": "ok"}
```

Call `Calf.listen` once, after creating the application. The middleware records
all HTTP routes, so individual route decorators are not required.

### 2. Start the dashboard

In one terminal, run:

```bash
calf --port 8765
```

The equivalent module command is:

```bash
python -m fastapi_calf.daemon --port 8765
```

### 3. Start the API

In another terminal, run the application:

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Requests to `http://127.0.0.1:8000` now appear in the dashboard.

## Production example

The middleware supports multiple Uvicorn workers. Start the dashboard first,
then start the application:

```bash
calf --port 8765
```

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

Each worker reports its PID, CPU use, memory use, request count, and the value
of `CUDA_VISIBLE_DEVICES` when that environment variable is set.

The monitor is an operational display, not a durable metrics store. Run it
under a process supervisor such as systemd, Supervisor, or your container
orchestrator when it needs to remain available.

## Configuration

`Calf.listen` accepts the following arguments:

```python
Calf.listen(app, host="127.0.0.1", port=8765)
```

| Argument | Default     | Purpose                                                        |
| -------- | ----------- | -------------------------------------------------------------- |
| `app`    | required    | FastAPI application on which the HTTP middleware is registered |
| `host`   | `127.0.0.1` | Address used by the application to connect to the dashboard    |
| `port`   | required    | TCP port used for monitoring events                            |

The port passed to `Calf.listen` must match the dashboard's `--port` value. It
is independent of the HTTP port used by Uvicorn.

The current dashboard binds to `127.0.0.1`. The API and dashboard therefore
need to run on the same machine or in the same network namespace. In separate
containers, `127.0.0.1` points to different containers, so this release needs
both processes in one container/pod network namespace to communicate.

## Optional route decorator

`@lookout` provides per-route instrumentation when the global middleware is not
being used. The endpoint must accept a FastAPI `Request` parameter named
`request`:

```python
from fastapi import FastAPI, Request
from fastapi_calf import lookout

app = FastAPI()


@app.post("/jobs")
@lookout
async def create_job(request: Request):
    payload = await request.json()
    return {"accepted": True, "job": payload}
```

Configure the destination before using decorator-only instrumentation if the
dashboard is not using the default `127.0.0.1:8765` destination:

```python
from fastapi_calf.config import config

config.host = "127.0.0.1"
config.port = 9000
```

Do not apply `@lookout` to a route already covered by `Calf.listen`; doing so
sends two events for one request and inflates the displayed metrics.

## What the dashboard reports

- Endpoint and HTTP method
- Total and failed request counts
- Average and most recent latency
- Most recent HTTP status
- Rolling latency and requests-per-second sparklines
- CPU and memory use across application workers
- Per-worker PID, resource use, request count, and GPU assignment

Worker statistics are collected from local operating-system process IDs. This
is another reason the dashboard should run alongside the monitored application.

## Operational behavior

- Event delivery uses a TCP connection to the configured dashboard for each
  request.
- Connection failures and timeouts are caught so monitoring cannot terminate
  an API request.
- Events are processed in memory and are not retained after the dashboard exits.
- The dashboard port carries monitoring data and should not be exposed publicly.
- Request bodies are not captured by the global middleware.
- High-volume deployments should load-test the monitoring overhead before
  enabling it in production.

## Troubleshooting

### No requests appear

Confirm that the dashboard is running, the two port values match, and
`Calf.listen(app, ...)` is called on the same application object served by
Uvicorn.

### The application logs connection errors

The dashboard is unavailable or listening on a different port. Start `calf`
before the API or correct the host and port configuration. These errors do not
stop the API from serving traffic.

### Worker CPU or memory is missing

The dashboard must be able to inspect the application's local process IDs. Run
the dashboard under the same operating-system user and in the same host or pod
as the API workers.

## Development and tests

Install the additional test dependencies and run pytest:

```bash
python -m pip install -r requirements-test.txt
python -m pytest
```

## License and stability

This is an early-stage project intended for experiments, internal tools, ML
pipelines, and proofs of concept. Review and load-test it before use on a
latency-sensitive production service.

