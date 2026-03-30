from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness_endpoint() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "service" in payload
