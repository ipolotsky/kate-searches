"""Контент-fetch: robots, троттлинг и анти-бот централизованы и переиспользуются
и скрапер-адаптером (в fetch), и стадией extract (дотяжка RSS/sitemap)."""

from app.fetch.base import FetchedPage, HtmlFetcher
from app.fetch.cascade import CascadeFetcher, default_chain
from app.fetch.crawl4ai_fetcher import Crawl4aiFetcher
from app.fetch.firecrawl_fetcher import FirecrawlFetcher
from app.fetch.httpx_fetcher import HttpxFetcher

__all__ = [
    "FetchedPage",
    "HtmlFetcher",
    "HttpxFetcher",
    "Crawl4aiFetcher",
    "FirecrawlFetcher",
    "CascadeFetcher",
    "default_chain",
]
