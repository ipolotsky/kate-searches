"""Адаптеры источников.

Новый тип источника = новый класс SourceAdapter с @AdapterRegistry.register.
Импорт модуля-адаптера ниже регистрирует его в реестре.
"""

from app.adapters.base import (
    AdapterCapabilities,
    BaseAdapter,
    FetchMode,
    FetchRequest,
    FetchResult,
    FetchStats,
    Raw,
    SourceAdapter,
    State,
)
from app.adapters.registry import REGISTRY, AdapterRegistry
from app.adapters.rss import RssAdapter, RssConfig
from app.adapters.scraper import ScraperAdapter, ScraperConfig
from app.adapters.sitemap import SitemapAdapter, SitemapConfig

__all__ = [
    "AdapterCapabilities",
    "BaseAdapter",
    "FetchMode",
    "FetchRequest",
    "FetchResult",
    "FetchStats",
    "Raw",
    "State",
    "SourceAdapter",
    "AdapterRegistry",
    "REGISTRY",
    "RssAdapter",
    "RssConfig",
    "SitemapAdapter",
    "SitemapConfig",
    "ScraperAdapter",
    "ScraperConfig",
]
