from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class _FakeParsed:
    def __init__(self, entries, etag=None, bozo=0):
        self.entries = entries
        self.etag = etag
        self.bozo = bozo


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_source_test_endpoint_dry_run_rss(monkeypatch):
    entries = [
        {
            "id": "g1",
            "link": "https://news.test/a?utm_source=x",
            "title": "Fresh drop",
            "summary": "s",
            "published_parsed": (2026, 7, 4, 10, 0, 0, 0, 0, 0),
        }
    ]
    monkeypatch.setattr(
        "app.adapters.rss.feedparser.parse", lambda url, etag=None: _FakeParsed(entries)
    )
    r = client.post("/internal/sources/test", json={"type": "rss", "url": "https://news.test/feed"})
    body = r.json()
    assert r.status_code == 200
    assert body["ok"] is True
    assert body["supported"] is True
    assert body["cursor_kind"] == "etag"
    assert len(body["sample"]) == 1
    assert body["sample"][0]["canonical_url"] == "https://news.test/a"
    assert "utm_source" not in body["sample"][0]["canonical_url"]


def test_source_test_endpoint_unknown_type():
    r = client.post("/internal/sources/test", json={"type": "carrier-pigeon", "url": "x"})
    body = r.json()
    assert body["ok"] is False
    assert body["supported"] is False
    assert body["error"] == "unsupported_type"
