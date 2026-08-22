from datetime import datetime, timezone


async def run_health_check(func_name, request, duration,):
    body = b""

    if request:
        body = await request.body()

    request_size = len(body)

    # headers are also part of the HTTP request size
    header_size = sum(
        len(key.encode()) + len(value.encode())
        for key, value in request.headers.items()
    )

    total_request_size = request_size + header_size

    timestamp = datetime.now(timezone.utc)

    print()
    print("Timestamp:", timestamp)
    print("Function:", func_name)
    print("Method:", request.method)
    print("Path:", request.url.path)
    print("Query params:", dict(request.query_params))

    print("Body size:", request_size, "bytes")
    print("Header size:", header_size, "bytes")
    print("Approx request size:", total_request_size, "bytes")

    print("Request time:", duration, "seconds")
    print("Latency:", duration * 1000, "ms")
    print()
