"""Tests for OpenAPI documentation."""


def test_openapi_schema_accessible(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "QALLM: Quality Assessment Tool"
    assert schema["info"]["version"] == "0.3.0"


def test_swagger_ui_accessible(client):
    r = client.get("/docs")
    assert r.status_code == 200
    assert "swagger-ui" in r.text.lower()


def test_redoc_accessible(client):
    r = client.get("/redoc")
    assert r.status_code == 200
    assert "redoc" in r.text.lower()


def test_openapi_has_tag_descriptions(client):
    schema = client.get("/openapi.json").json()
    tags = {t["name"]: t["description"] for t in schema.get("tags", [])}
    assert "session" in tags
    assert "analysis" in tags
    assert "health" in tags
