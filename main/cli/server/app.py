from fastapi import FastAPI, Request

from ..decorator import observer_block


app = FastAPI()


@app.get("/health")
@observer_block
def health(request: Request):
    return {"message": "healthy"}


@app.get("/users")
@observer_block
def users(request: Request):
    return {"users": ["alice", "bob"]}


@app.post("/process")
@observer_block
async def process(request: Request):
    raw_body = await request.body()

    if raw_body:
        body = await request.json()
    else:
        body = None

    return {
        "received": body
    }
