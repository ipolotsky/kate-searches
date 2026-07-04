"""Scraper-адаптер: одностраничный fetch (мок CascadeFetcher) + extract в normalize."""

from datetime import UTC, datetime

from app.adapters.base import FetchRequest
from app.adapters.scraper import ScraperAdapter
from app.fetch.base import FetchedPage

_SOURCE = {
    "id": "22222222-2222-2222-2222-222222222222",
    "tenant_id": "t-1",
    "url": "https://shop.test/news/drop",
    "config": {},
}

_PARAGRAPH = (
    "The fashion house unveiled a reissued archive collection this morning in Milan, featuring "
    "leather jackets and hand stitched denim pieces that first appeared decades ago on its "
    "original runways. Resale specialists expect strong collector demand for the rare designer "
    "items across the region this season, noting that archival drops consistently outperform "
    "current ready to wear lines at auction. Editors who attended the private showing described "
    "the reissues as faithful to the house codes while updated with modern sizing and materials, "
    "a combination that historically drives both primary sales and secondary market interest."
)
_HTML = f"""
<html><head><title>Archive drop</title><meta name="date" content="2026-07-04"></head>
<body><article><h1>Heritage house reissues archive jackets</h1>
<p>{_PARAGRAPH}</p>
</article></body></html>
"""


class _FakeCascade:
    def __init__(self, *args, **kwargs):
        pass

    def fetch_html(self, url, *, render_js=False, timeout=None):
        return FetchedPage(html=_HTML, status=200, final_url=url, fetcher="httpx")


def test_scraper_fetch_returns_single_page(monkeypatch) -> None:
    monkeypatch.setattr("app.adapters.scraper.CascadeFetcher", _FakeCascade)
    result = ScraperAdapter().fetch(FetchRequest(source=_SOURCE, state={}))
    assert len(result.items) == 1
    assert result.items[0]["html"].startswith("\n<html>")
    assert result.items[0]["usable"] is True


def test_scraper_normalize_extracts_full_body() -> None:
    raw = {"url": "https://shop.test/news/drop", "html": _HTML, "usable": True}
    doc = ScraperAdapter().normalize(_SOURCE, raw)
    assert doc.source_type == "scraper"
    assert doc.body_is_complete is True
    assert "jackets" in doc.body.lower()
    assert doc.published_at == datetime(2026, 7, 4, tzinfo=UTC)
    assert doc.metadata.get("dateless") is None


def test_scraper_fetch_empty_page_warns(monkeypatch) -> None:
    class _Empty(_FakeCascade):
        def fetch_html(self, url, *, render_js=False, timeout=None):
            return FetchedPage(html="", status=0, error="boom", fetcher="httpx")

    monkeypatch.setattr("app.adapters.scraper.CascadeFetcher", _Empty)
    result = ScraperAdapter().fetch(FetchRequest(source=_SOURCE, state={}))
    assert result.items == []
    assert "boom" in result.warnings
