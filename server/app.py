from fastapi import FastAPI, Request
from fastapi_calf import lookout, Calf


app = FastAPI()

Calf.listen(app, port=8008)


@app.get("/health")
def health():
    return {"message": "healthy"}


@app.get("/users")
def users():
    return {"users": ["alice", "bob"]}


@app.post("/process")
async def process():
    raw_body = await request.body()

    if raw_body:
        body = await request.json()
    else:
        body = None

    return {
        "received": body
    }
