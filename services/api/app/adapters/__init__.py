"""Реестр адаптеров источников.

Новый тип источника = новый класс, реализующий SourceAdapter, + запись в REGISTRY.
"""

from app.adapters.base import Raw, SourceAdapter
from app.adapters.rss import RssAdapter

REGISTRY: dict[str, type[SourceAdapter]] = {
    "rss": RssAdapter,
    # "scraper": ScraperAdapter,   # TODO M1: Crawl4AI/Firecrawl
    # "sitemap": SitemapAdapter,   # TODO M1: news-sitemap
    # "telegram": TelegramAdapter, # TODO фаза 2
    # "reddit": RedditAdapter,     # TODO фаза 2
}

__all__ = ["Raw", "SourceAdapter", "RssAdapter", "REGISTRY"]
