"""Канонизация URL, новизна и дедуп.

Каскад: URL-канонизация -> хеш контента -> (TODO) near-dup simhash.
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse, urlunparse

_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "ref", "ref_src")


def canonicalize_url(url: str) -> str:
    """Срезать трекинг-параметры, нормализовать схему/хост/слеши."""
    if not url:
        return url
    p = urlparse(url.strip())
    scheme = (p.scheme or "https").lower()
    if scheme == "http":
        scheme = "https"
    netloc = p.netloc.lower()
    path = p.path.rstrip("/") or "/"
    # выкидываем трекинг-параметры
    query_parts = []
    for kv in p.query.split("&"):
        if not kv:
            continue
        key = kv.split("=", 1)[0]
        if any(key.startswith(pref) for pref in _TRACKING_PREFIXES):
            continue
        query_parts.append(kv)
    query = "&".join(sorted(query_parts))
    return urlunparse((scheme, netloc, path, "", query, ""))


def is_fresh(published_at: datetime, tz_now: datetime | None = None, days: int = 1) -> bool:
    """Новость считается свежей, если опубликована не раньше, чем `days` назад."""
    now = tz_now or datetime.now(UTC)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    return published_at >= now - timedelta(days=days)
