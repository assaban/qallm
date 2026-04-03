"""Tests for the /api/health endpoint."""


def test_health_returns_200(client):
    res = client.get("/api/health")
    assert res.status_code == 200


def test_health_reports_healthy(client):
    data = client.get("/api/health").json()
    assert data["status"] == "healthy"
    assert data["service"] == "qallm"
    assert "version" in data
