"""Канонизация URL, новизна и дедуп-каскад.

Слои дедупа (все до скоринга): URL-канон -> content-hash-exact -> simhash near-dup ->
кросс-источниковый priority-тай-брейк. Окно и скан — параметр стратегии (DedupStrategy),
чтобы pgvector-слой фазы 2 встал без правки границ.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import blake2b, sha256
from typing import Literal
from urllib.parse import urlparse, urlunparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "ref", "ref_src")
_WORD_RE = re.compile(r"\w+", re.UNICODE)
_WS_RE = re.compile(r"\s+", re.UNICODE)

_MASK64 = (1 << 64) - 1
_SIGN_OFFSET = 1 << 63


# ─────────────────────────────────────────── URL-канонизация


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


# ─────────────────────────────────────────── Новизна (AC-1)


def normalize_timezone(tz: str | None) -> str:
    """Валидировать таймзону через zoneinfo, fallback UTC. Использовать при записи tenants."""
    if not tz:
        return "UTC"
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return "UTC"
    return tz


def _safe_zone(tz: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def is_fresh(published_at: datetime, tz_now: datetime | None = None, days: int = 1) -> bool:
    """Устаревшая проверка свежести (оставлена для обратной совместимости тестов)."""
    now = tz_now or datetime.now(UTC)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    return published_at >= now - timedelta(days=days)


def novelty_boundary(
    tenant_timezone: str,
    *,
    now_utc: datetime | None = None,
    novelty_days: int = 0,
    lookback_hours: int = 0,
) -> datetime:
    """UTC-момент полуночи сегодняшнего дня в tz тенанта минус окно/грейс."""
    now = now_utc or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    zone = _safe_zone(tenant_timezone)
    local_now = now.astimezone(zone)
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    boundary_local = local_midnight - timedelta(days=novelty_days)
    return boundary_local.astimezone(UTC) - timedelta(hours=lookback_hours)


def is_novel(
    published_at: datetime | None,
    tenant_timezone: str,
    *,
    now_utc: datetime | None = None,
    lookback_hours: int = 0,
    novelty_days: int = 0,
    mode: Literal["incremental", "backfill", "test"] = "incremental",
    since: datetime | None = None,
) -> bool:
    """Свежесть по календарной tz тенанта.

    Граница — полночь сегодняшнего дня в tz тенанта, приведённая к UTC, минус lookback-грейс.
    В backfill граница — since (без today-гейта). Статья без даты в дневное окно не берётся.
    """
    if published_at is None:
        return False
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)

    if mode == "backfill":
        if since is None:
            return True
        if since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        return published_at >= since

    boundary_utc = novelty_boundary(
        tenant_timezone,
        now_utc=now_utc,
        novelty_days=novelty_days,
        lookback_hours=lookback_hours,
    )
    return published_at >= boundary_utc


# ─────────────────────────────────────────── Контент-хеш и simhash


def normalize_text(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").strip()).lower()


def content_hash(text: str) -> str:
    """sha256 нормализованного тела — точная синдикация под разными URL."""
    return sha256(normalize_text(text).encode("utf-8")).hexdigest()


def _feature_hash(token: str) -> int:
    return int.from_bytes(blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")


def simhash64(text: str) -> int:
    """64-битный SimHash-отпечаток (unsigned). Пустой текст -> 0."""
    tokens = _WORD_RE.findall(normalize_text(text))
    if not tokens:
        return 0
    vector = [0] * 64
    for token in tokens:
        h = _feature_hash(token)
        for bit in range(64):
            if (h >> bit) & 1:
                vector[bit] += 1
            else:
                vector[bit] -= 1
    fingerprint = 0
    for bit in range(64):
        if vector[bit] > 0:
            fingerprint |= 1 << bit
    return fingerprint & _MASK64


def hamming(a: int, b: int) -> int:
    """Расстояние Хэмминга между двумя unsigned 64-битными отпечатками."""
    return ((a ^ b) & _MASK64).bit_count()


def to_signed(unsigned: int) -> int:
    """unsigned 64-бит -> signed bigint для колонки simhash."""
    return (unsigned & _MASK64) - _SIGN_OFFSET


def to_unsigned(signed: int) -> int:
    """signed bigint из колонки simhash -> unsigned 64-бит для hamming."""
    return (signed + _SIGN_OFFSET) & _MASK64


# ─────────────────────────────────────────── Кросс-источниковый тай-брейк


def is_better_canonical(
    priority_a: int | None,
    published_a: datetime | None,
    priority_b: int | None,
    published_b: datetime | None,
) -> bool:
    """a строго лучше b: higher priority выигрывает, при равенстве — раньше опубликован."""
    pa = priority_a if priority_a is not None else 0
    pb = priority_b if priority_b is not None else 0
    if pa != pb:
        return pa > pb
    if published_a is not None and published_b is not None and published_a != published_b:
        return published_a < published_b
    return False


# ─────────────────────────────────────────── Стратегии дедупа (шов расширяемости)

DedupMethod = Literal["url", "content_hash", "simhash", "embedding"]
DedupWindow = Literal["none", "daily", "tenant"]


@dataclass(frozen=True)
class DedupStrategy:
    name: str
    method: DedupMethod
    window: DedupWindow
    threshold: int | None = None


DEFAULT_STRATEGIES: tuple[DedupStrategy, ...] = (
    DedupStrategy("url_canonical", "url", "none"),
    DedupStrategy("content_exact", "content_hash", "daily"),
    DedupStrategy("simhash_near", "simhash", "daily", threshold=3),
)
