from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_source_test_endpoint_knows_rss():
    r = client.post("/internal/sources/test", json={"type": "rss", "url": "https://x/feed"})
    assert r.status_code == 200
    assert r.json()["supported"] is True


def test_source_test_endpoint_unknown_type():
    r = client.post("/internal/sources/test", json={"type": "carrier-pigeon", "url": "x"})
    assert r.json()["supported"] is False
