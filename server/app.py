import asyncio

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi_calf import Calf
from pydantic import BaseModel
from typing import Any
import time
# import torch

# device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# print(device)


app = FastAPI()

Calf.listen(app, port=8765, server="test_server", block_threshold=50, block_check_interval=20, dashboard_path="/calf")


class LifecyclePayload(BaseModel):
    message: str


async def lifecycle_dependency():
    await asyncio.sleep(0.03)


def lifecycle_background_task():
    time.sleep(0.04)


@app.get("/health")
def health():
    return {"message": "healthy"}


@app.get("/users")
def users():
    return {"users": ["alice", "bob"]}


@app.get("/block-event-loop")
async def block_event_loop():
    """Intentional anti-pattern used to test Calf's blocking detector."""
    time.sleep(0.5)
    return {"message": "event loop was blocked for 500 ms"}


@app.get("/cooperative-sleep")
async def cooperative_sleep():
    """The async equivalent should not produce a blocking warning."""
    await asyncio.sleep(0.5)
    return {"message": "event loop remained available"}


@app.post("/lifecycle", response_model=LifecyclePayload)
async def lifecycle_demo(
    payload: LifecyclePayload,
    background_tasks: BackgroundTasks,
    _dependency=Depends(lifecycle_dependency),
):
    """Exercise every lifecycle timer with small, visible delays."""
    await asyncio.sleep(0.02)
    background_tasks.add_task(lifecycle_background_task)
    return payload


@app.post("/translate")
def translate(background_tasks: BackgroundTasks):
    background_tasks.add_task(dummy_slow_translation)
    return {"message": "translation queued"}


def dummy_slow_translation():
    time.sleep(60)
    print("Dummy translation completed")


@app.post("/process")
async def process(request: Request):
    raw_body = await request.body()

    if raw_body:
        body = await request.json()
    else:
        body = None

    return {"received": body}
