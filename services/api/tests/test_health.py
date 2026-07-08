from contextlib import contextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main_mod
from app.main import app

client = TestClient(app)


class _FakeParsed:
    def __init__(self, entries, etag=None, bozo=0):
        self.entries = entries
        self.etag = etag
        self.bozo = bozo


class _FakeResponse:
    def __init__(self, status_code, content, headers):
        self.status_code = status_code
        self.content = content
        self.headers = headers


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_ok_when_dependencies_up(monkeypatch):
    @contextmanager
    def fake_connect():
        yield SimpleNamespace(execute=lambda *a, **k: None)

    import redis

    monkeypatch.setattr(main_mod.engine, "connect", fake_connect)
    monkeypatch.setattr(
        redis.Redis, "from_url", staticmethod(lambda *a, **k: SimpleNamespace(ping=lambda: True))
    )
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] == "ok"


def test_ready_503_when_database_down(monkeypatch):
    def boom():
        raise RuntimeError("db down")

    import redis

    monkeypatch.setattr(main_mod.engine, "connect", boom)
    monkeypatch.setattr(
        redis.Redis, "from_url", staticmethod(lambda *a, **k: SimpleNamespace(ping=lambda: True))
    )
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["database"] == "down"


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
    monkeypatch.setattr("app.adapters.rss.feedparser.parse", lambda content: _FakeParsed(entries))
    monkeypatch.setattr(
        "app.adapters.rss.safe_get",
        lambda url, *, headers, timeout: _FakeResponse(200, b"<rss/>", {}),
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


def test_adapters_endpoint_describes_registered_adapters():
    r = client.get("/internal/adapters")
    assert r.status_code == 200
    adapters = r.json()["adapters"]
    by_type = {a["type"]: a for a in adapters}
    assert {"rss", "sitemap", "scraper"} <= set(by_type)
    for adapter in adapters:
        assert "capabilities" in adapter
        assert adapter["config_schema"]["type"] == "object"
    # config_schema drives the UI source form; rss exposes novelty_days
    assert "novelty_days" in by_type["rss"]["config_schema"]["properties"]
