from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from main import health

app = FastAPI()

@app.get("/")
@health
def home():
    return {"message": "FastAPI server is running"}

client = TestClient(app)

def test_health_decorator(capsys):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "FastAPI server is running"
    }

    output = capsys.readouterr()
    print(output.out)
    assert "returning health" in output.out
