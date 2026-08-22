from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

from main import health


app = FastAPI()


class Item(BaseModel):
    name: str
    quantity: int


@app.get("/health")
@health
def health_api(request: Request):
    return {"message": "FastAPI server is running"}


@app.get("/items")
@health
def get_items(request: Request, limit: int):
    return {"limit": limit}


@app.post("/items")
@health
def create_item(request: Request, item: Item, notify: bool = False):
    return {"item": item.model_dump(), "notify": notify}


client = TestClient(app)


def read_and_print_output(capsys):
    output = capsys.readouterr().out

    with capsys.disabled():
        print(output, end="")

    return output


def test_get_api(capsys):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"message": "FastAPI server is running"}

    output = read_and_print_output(capsys)
    assert "Method: GET" in output
    assert "Path: /health" in output
    assert "Query params: {}" in output
    assert "Body: None" in output


def test_get_api_with_query_parameter(capsys):
    response = client.get("/items", params={"limit": 5})

    assert response.status_code == 200
    assert response.json() == {"limit": 5}

    output = read_and_print_output(capsys)
    assert "Method: GET" in output
    assert "Path: /items" in output
    assert "Query params: {'limit': '5'}" in output
    assert "Body: None" in output


def test_post_api_with_body_and_query_parameter(capsys):
    response = client.post(
        "/items",
        params={"notify": "true"},
        json={"name": "Keyboard", "quantity": 2},
    )

    assert response.status_code == 200
    assert response.json() == {
        "item": {"name": "Keyboard", "quantity": 2},
        "notify": True,
    }

    output = read_and_print_output(capsys)
    assert "Method: POST" in output
    assert "Path: /items" in output
    assert "Query params: {'notify': 'true'}" in output
    assert 'Body: {"name":"Keyboard","quantity":2}' in output
