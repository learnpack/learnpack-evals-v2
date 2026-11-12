from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_ok(requires_db):
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_livez_does_not_need_a_database():
    # No `requires_db` on purpose: the host probes this endpoint every few seconds, and a
    # probe that reached the database would keep Neon's compute from ever suspending.
    with TestClient(app) as client:
        response = client.get("/livez")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
