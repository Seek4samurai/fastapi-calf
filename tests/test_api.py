from unittest.mock import patch

from fastapi.testclient import TestClient


# Importing the app normally announces the process to fastapi-calf. Avoid opening
# a monitoring socket in these correctness tests.
with patch("fastapi_calf.calf.emit_event"):
    from server.app import app


client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"message": "healthy"}


def test_users():
    response = client.get("/users")

    assert response.status_code == 200
    assert response.json() == {"users": ["alice", "bob"]}


def test_process_with_json_body():
    payload = {"job": "load-test", "items": [1, 2, 3]}
    response = client.post("/process", json=payload)

    assert response.status_code == 200
    assert response.json() == {"received": payload}


def test_process_without_body():
    response = client.post("/process")

    assert response.status_code == 200
    assert response.json() == {"received": None}
