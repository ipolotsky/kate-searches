"""Каскад fetcher-ов: эскалация дёшево->дорого по КАЧЕСТВУ извлечения.

httpx -> crawl4ai (JS) -> firecrawl (платный). Переход к следующему при пустом/тонком
теле или анти-бот сигнале, а не заранее. Платные fetcher-ы включаются только при
allow_paid (dry-run теста источника их запрещает).
"""

from app.config import settings
from app.fetch.base import FetchedPage, HtmlFetcher, is_usable
from app.fetch.crawl4ai_fetcher import Crawl4aiFetcher
from app.fetch.firecrawl_fetcher import FirecrawlFetcher
from app.fetch.httpx_fetcher import HttpxFetcher


def default_chain() -> list[HtmlFetcher]:
    return [HttpxFetcher(), Crawl4aiFetcher(), FirecrawlFetcher()]


class CascadeFetcher:
    def __init__(
        self,
        fetchers: list[HtmlFetcher] | None = None,
        *,
        allow_paid: bool = False,
        min_chars: int | None = None,
    ) -> None:
        self.fetchers = fetchers if fetchers is not None else default_chain()
        self.allow_paid = allow_paid
        self.min_chars = min_chars if min_chars is not None else settings.extract_body_min_chars

    def fetch_html(
        self, url: str, *, render_js: bool = False, timeout: float | None = None
    ) -> FetchedPage:
        last: FetchedPage | None = None
        for fetcher in self.fetchers:
            if getattr(fetcher, "requires_js", False) and not render_js:
                continue
            if getattr(fetcher, "is_paid", False) and not self.allow_paid:
                continue
            page = fetcher.fetch_html(url, render_js=render_js, timeout=timeout)
            last = page
            if is_usable(page, self.min_chars):
                return page
        if last is not None:
            return last
        return FetchedPage(final_url=url, error="no_fetcher_available")
