"""RSS и sitemap адаптеры: fetch по курсору, dateless-гейт, парсинг XML/index."""

import time
from datetime import UTC, datetime

from app.adapters.base import FetchRequest
from app.adapters.rss import RssAdapter
from app.adapters.sitemap import SitemapAdapter, parse_sitemap

_SOURCE = {
    "id": "11111111-1111-1111-1111-111111111111",
    "tenant_id": "t-1",
    "url": "https://feed.test/rss",
    "config": {},
}


class _FakeParsed:
    def __init__(self, entries, etag=None, bozo=0):
        self.entries = entries
        self.etag = etag
        self.bozo = bozo


def _struct_time(dt: datetime) -> time.struct_time:
    return dt.timetuple()


# ─────────────────────────────────────────── RSS


def test_rss_normalize_sets_date_and_body_complete() -> None:
    long_body = "x" * 600
    raw = {
        "id": "guid-1",
        "link": "https://Example.com/News/Item/?utm_source=x",
        "title": "  Hello  ",
        "summary": "short summary",
        "content": [{"value": long_body}],
        "published_parsed": _struct_time(datetime(2026, 7, 4, 10, tzinfo=UTC)),
        "tags": [{"term": "fashion"}],
    }
    doc = RssAdapter().normalize(_SOURCE, raw)
    assert doc.title == "Hello"
    assert doc.published_at == datetime(2026, 7, 4, 10, tzinfo=UTC)
    assert doc.body_is_complete is True
    assert doc.canonical_url == "https://example.com/News/Item"
    assert "utm_source" not in doc.canonical_url
    assert doc.metadata.get("dateless") is None


def test_rss_normalize_dateless_flag() -> None:
    raw = {"id": "g", "link": "https://x.test/a", "title": "t", "summary": "s"}
    doc = RssAdapter().normalize(_SOURCE, raw)
    assert doc.published_at is None
    assert doc.metadata["dateless"] is True
    assert doc.body_is_complete is False


def test_rss_fetch_dedups_seen_and_respects_limit(monkeypatch) -> None:
    entries = [{"id": f"g{i}", "link": f"https://x.test/{i}", "title": f"t{i}"} for i in range(5)]
    monkeypatch.setattr(
        "app.adapters.rss.feedparser.parse",
        lambda url, etag=None: _FakeParsed(entries, etag="etag-1"),
    )
    adapter = RssAdapter()
    result = adapter.fetch(FetchRequest(source=_SOURCE, state={"seen_guids": ["g0", "g1"]}))
    returned = {item["id"] for item in result.items}
    assert returned == {"g2", "g3", "g4"}
    assert result.state["etag"] == "etag-1"
    assert "g4" in result.state["seen_guids"]

    limited = adapter.fetch(FetchRequest(source=_SOURCE, state={}, mode="test", limit=2))
    assert len(limited.items) == 2


def test_rss_fetch_empty_feed_warns(monkeypatch) -> None:
    monkeypatch.setattr("app.adapters.rss.feedparser.parse", lambda url, etag=None: _FakeParsed([]))
    result = RssAdapter().fetch(FetchRequest(source=_SOURCE, state={}))
    assert "empty_feed" in result.warnings
    assert result.items == []


# ─────────────────────────────────────────── Sitemap

_URLSET = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  <url>
    <loc>https://news.test/a</loc>
    <news:news>
      <news:publication><news:language>en</news:language></news:publication>
      <news:publication_date>2026-07-04T10:00:00Z</news:publication_date>
      <news:title>Article A</news:title>
    </news:news>
    <lastmod>2026-07-04</lastmod>
  </url>
  <url>
    <loc>https://news.test/b</loc>
    <lastmod>2026-07-03</lastmod>
  </url>
</urlset>"""

_INDEX = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://news.test/news-sitemap.xml</loc></sitemap>
</sitemapindex>"""


def test_parse_urlset_entries() -> None:
    parsed = parse_sitemap(_URLSET)
    assert parsed["kind"] == "urlset"
    entries = parsed["entries"]
    assert len(entries) == 2
    assert entries[0]["loc"] == "https://news.test/a"
    assert entries[0]["title"] == "Article A"
    assert entries[0]["language"] == "en"
    assert entries[0]["published_at"] == datetime(2026, 7, 4, 10, tzinfo=UTC)
    # второй элемент датируется по lastmod
    assert entries[1]["published_at"] == datetime(2026, 7, 3, tzinfo=UTC)


def test_parse_sitemap_index() -> None:
    parsed = parse_sitemap(_INDEX)
    assert parsed["kind"] == "index"
    assert parsed["children"] == ["https://news.test/news-sitemap.xml"]


def test_parse_sitemap_recovers_from_garbage() -> None:
    parsed = parse_sitemap(b"<broken><url><loc>https://x.test/a</loc>")
    assert parsed["kind"] == "urlset"
    assert [e["loc"] for e in parsed["entries"]] == ["https://x.test/a"]


def test_sitemap_fetch_follows_index_and_advances_cursor(monkeypatch) -> None:
    def fake_download(url: str) -> bytes:
        return _INDEX if url.endswith("index.xml") else _URLSET

    monkeypatch.setattr("app.adapters.sitemap._download", fake_download)
    adapter = SitemapAdapter()
    source = {**_SOURCE, "url": "https://news.test/index.xml"}
    result = adapter.fetch(FetchRequest(source=source, state={}))
    locs = {item["loc"] for item in result.items}
    assert locs == {"https://news.test/a", "https://news.test/b"}
    assert result.state["last_published_at"] == datetime(2026, 7, 4, 10, tzinfo=UTC).isoformat()


def test_sitemap_fetch_incremental_skips_old(monkeypatch) -> None:
    monkeypatch.setattr("app.adapters.sitemap._download", lambda url: _URLSET)
    adapter = SitemapAdapter()
    source = {**_SOURCE, "url": "https://news.test/news-sitemap.xml"}
    state = {"last_published_at": datetime(2026, 7, 3, 12, tzinfo=UTC).isoformat()}
    result = adapter.fetch(FetchRequest(source=source, state=state))
    locs = {item["loc"] for item in result.items}
    assert locs == {"https://news.test/a"}


def test_sitemap_normalize_thin_body() -> None:
    raw = {
        "loc": "https://news.test/a",
        "title": "A",
        "published_at": datetime(2026, 7, 4, tzinfo=UTC),
    }
    doc = SitemapAdapter().normalize({**_SOURCE, "url": "x"}, raw)
    assert doc.body_is_complete is False
    assert doc.source_type == "sitemap"
    assert doc.canonical_url == "https://news.test/a"
