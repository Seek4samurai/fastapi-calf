# Testing

Install the test dependencies once:

```powershell
python -m pip install -r requirements-test.txt
```

Run the endpoint correctness tests:

```powershell
python -m pytest tests/test_api.py -q
```

Run the live load test. It starts the sample API with four Uvicorn workers,
checks every endpoint, sends 100 requests concurrently, prints throughput and
latency statistics, and shuts the server down:

```powershell
python -m tests.load_test
```

Useful overrides:

```powershell
python -m tests.load_test --requests 100 --concurrency 50 --workers 4
python -m tests.load_test --url http://127.0.0.1:9000 --external-server
```

For the monitoring dashboard, start `fastapi-calf` on port 8005 in another
terminal before the load test. The API continues to work when the dashboard is
not running.
