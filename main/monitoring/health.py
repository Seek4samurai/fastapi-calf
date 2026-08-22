from datetime import datetime, timezone
from fastapi import Request


async def run_health_check(func_name, request):
    body = None

    if request:
        raw_body = await request.body()

        if raw_body:
            body = raw_body.decode("utf-8")

    print("")
    print("Method:", request.method)
    print("Path:", request.url.path)
    print("Query params:", dict(request.query_params))
    print("Body:", body)
    print("")
