from fastapi import FastAPI, Request
from fastapi_calf import Calf
from typing import Any
# import torch

# device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# print(device)


app = FastAPI()

Calf.listen(app, port=8765, server="test_server")


@app.get("/health")
def health():
    return {"message": "healthy"}


@app.get("/users")
def users():
    return {"users": ["alice", "bob"]}


@app.post("/translate")
def users():

    return {"message": "done..."}


@app.post("/process")
async def process(request: Request):
    raw_body = await request.body()

    if raw_body:
        body = await request.json()
    else:
        body = None

    return {"received": body}
