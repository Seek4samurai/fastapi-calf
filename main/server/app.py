from fastapi import FastAPI, Request
from fastapi_calf import lookout, Calf


app = FastAPI()

Calf.listen(port=8005)


@app.get("/health")
@lookout
def health(request: Request):
    return {"message": "healthy"}


@app.get("/users")
@lookout
def users(request: Request):
    return {"users": ["alice", "bob"]}


@app.post("/process")
@lookout
async def process(request: Request):
    raw_body = await request.body()

    if raw_body:
        body = await request.json()
    else:
        body = None

    return {
        "received": body
    }
