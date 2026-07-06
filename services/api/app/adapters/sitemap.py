"""Sitemap-адаптер: news-sitemap и sitemap-index.

Тело тонкое (loc + заголовок) — стадия extract гидратирует полное тело. Курсор —
TimestampCursor по publication_date/lastmod. Парсинг XML вынесен в чистые функции
(parse_sitemap/extract_entries), сеть — в _download (монкипатчится в тестах).
"""

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from lxml import etree
from pydantic import BaseModel

from app.adapters.base import (
    AdapterCapabilities,
    BaseAdapter,
    FetchRequest,
    FetchResult,
    FetchStats,
    Raw,
)
from app.adapters.cursors import TimestampCursor
from app.adapters.registry import AdapterRegistry
from app.config import settings
from app.models import Document
from app.pipeline.dedup import canonicalize_url, content_hash

_MAX_CHILD_SITEMAPS = 25


class SitemapConfig(BaseModel):
    language: str | None = None
    max_urls: int = 200
    follow_index: bool = True
    novelty_days: int = 0


@AdapterRegistry.register
class SitemapAdapter(BaseAdapter):
    type = "sitemap"
    capabilities = AdapterCapabilities(
        cursor_kind="timestamp",
        supports_incremental=True,
        supports_backfill=True,
        provides_full_text=False,
        needs_javascript=False,
        respects_robots=True,
        emits_media=False,
        default_rate_limit_rpm=30,
    )
    config_model = SitemapConfig

    def fetch(self, request: FetchRequest) -> FetchResult:
        config = self.validate_config(request.source.get("config") or {})
        cursor = TimestampCursor.from_state(request.state)
        warnings: list[str] = []

        root_xml = _download(request.source["url"])
        parsed = parse_sitemap(root_xml)

        entries: list[dict]
        if parsed["kind"] == "index":
            entries = []
            if not config.follow_index:
                warnings.append("index_not_followed")
            else:
                for child in parsed["children"][:_MAX_CHILD_SITEMAPS]:
                    try:
                        child_parsed = parse_sitemap(_download(child))
                    except Exception:
                        warnings.append("child_fetch_error")
                        continue
                    entries.extend(child_parsed.get("entries", []))
        else:
            entries = parsed["entries"]

        if not entries:
            warnings.append("empty_sitemap")

        fetched = len(entries)
        incremental = request.mode == "incremental"
        # Сортируем по дате ASC (dateless — в конец): при усечении по max_urls курсор двигается
        # только до max выбранных, а более новые невыбранные записи не «перепрыгиваются» и
        # дочитываются в следующих прогонах (без молчаливой потери).
        entries.sort(key=_sort_key)

        selected: list[Raw] = []
        max_seen = cursor.last_published_at
        for entry in entries:
            published = entry.get("published_at")
            if (
                incremental
                and cursor.last_published_at is not None
                and published is not None
                and published <= cursor.last_published_at
            ):
                continue
            selected.append(entry)
            if published is not None and (max_seen is None or published > max_seen):
                max_seen = published
            if request.limit is not None and len(selected) >= request.limit:
                break
            if len(selected) >= config.max_urls:
                break

        cursor.last_published_at = max_seen
        stats = FetchStats(fetched=fetched, new=len(selected), skipped=fetched - len(selected))
        return FetchResult(
            items=selected,
            state=cursor.to_state(),
            has_more=False,
            warnings=warnings,
            stats=stats,
        )

    def normalize(self, source: dict, raw: Raw) -> Document:
        url = raw.get("loc") or ""
        canonical = canonicalize_url(url)
        published = raw.get("published_at")
        config = source.get("config") or {}
        title = (raw.get("title") or "").strip()
        body = title
        metadata: dict = {"sitemap": True}
        if published is None:
            metadata["dateless"] = True

        return Document(
            id=sha256(f"{source.get('id')}:{canonical}".encode()).hexdigest(),
            tenant_id=str(source["tenant_id"]),
            source_id=str(source["id"]) if source.get("id") else "",
            source_type="sitemap",
            url=url,
            canonical_url=canonical,
            external_id=raw.get("loc"),
            title=title,
            body=body,
            summary=None,
            language=raw.get("language") or config.get("language"),
            author=None,
            published_at=published,
            fetched_at=datetime.now(UTC),
            content_hash=content_hash(body),
            body_is_complete=False,
            metadata=metadata,
        )


_MIN_AWARE = datetime.min.replace(tzinfo=UTC)


def _sort_key(entry: dict) -> tuple[bool, datetime]:
    published = entry.get("published_at")
    return (published is None, published or _MIN_AWARE)


def _localname(element: Any) -> str:
    return etree.QName(element).localname


def parse_sitemap(xml: bytes) -> dict:
    """Разобрать sitemap-index или urlset. Возвращает {kind, children|entries}."""
    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True)
    root = etree.fromstring(xml, parser=parser)
    if root is None:
        return {"kind": "urlset", "entries": []}
    tag = _localname(root)
    if tag == "sitemapindex":
        children = [
            (loc.text or "").strip()
            for loc in root.iter()
            if _localname(loc) == "loc" and (loc.text or "").strip()
        ]
        return {"kind": "index", "children": children}
    return {"kind": "urlset", "entries": extract_entries(root)}


def extract_entries(root: Any) -> list[dict]:
    entries: list[dict] = []
    for url_el in root.iter():
        if _localname(url_el) != "url":
            continue
        loc = None
        published_raw = None
        lastmod_raw = None
        title = None
        language = None
        for child in url_el.iter():
            name = _localname(child)
            value = (child.text or "").strip()
            if name == "loc" and loc is None:
                loc = value
            elif name == "publication_date" and published_raw is None:
                published_raw = value
            elif name == "lastmod" and lastmod_raw is None:
                lastmod_raw = value
            elif name == "title" and title is None:
                title = value
            elif name == "language" and language is None:
                language = value
        if not loc:
            continue
        entries.append(
            {
                "loc": loc,
                "title": title,
                "language": language,
                "published_at": _parse_iso(published_raw) or _parse_iso(lastmod_raw),
            }
        )
    return entries


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(value.strip()[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _download(url: str) -> bytes:
    from app.fetch.guard import safe_get

    headers = {"User-Agent": settings.user_agent}
    response = safe_get(url, headers=headers, timeout=settings.fetch_timeout_seconds)
    response.raise_for_status()
    return response.content
