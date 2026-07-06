"""RSS/Atom адаптер на новом контракте.

GUID — ключ идентичности (fallback на link). pubDate — только для датирования; при его
отсутствии статья помечается dateless и не проходит гейт новизны (AC-1). ETag + окно
виденных guid живут в ETagCursor. body_is_complete выставляется по длинному content:encoded.
"""

from datetime import UTC, datetime
from hashlib import sha256

import feedparser
from pydantic import BaseModel

from app.adapters.base import (
    AdapterCapabilities,
    BaseAdapter,
    FetchRequest,
    FetchResult,
    FetchStats,
    Raw,
)
from app.adapters.cursors import ETagCursor
from app.adapters.registry import AdapterRegistry
from app.fetch.guard import BlockedUrlError, assert_public_url
from app.models import Document
from app.pipeline.dedup import canonicalize_url, content_hash

_FULL_BODY_MIN = 500


class RssConfig(BaseModel):
    language: str | None = None
    full_text_fetch: bool = True
    novelty_days: int = 0


@AdapterRegistry.register
class RssAdapter(BaseAdapter):
    type = "rss"
    capabilities = AdapterCapabilities(
        cursor_kind="etag",
        supports_incremental=True,
        supports_backfill=False,
        provides_full_text=False,
        needs_javascript=False,
        respects_robots=True,
        emits_media=True,
        default_rate_limit_rpm=60,
    )
    config_model = RssConfig

    def fetch(self, request: FetchRequest) -> FetchResult:
        cursor = ETagCursor.from_state(request.state)
        seen = set(cursor.seen_guids)
        try:
            assert_public_url(request.source["url"])
        except BlockedUrlError:
            return FetchResult(items=[], state=cursor.to_state(), warnings=["blocked_url"])
        parsed = feedparser.parse(request.source["url"], etag=cursor.etag)

        warnings: list[str] = []
        if getattr(parsed, "bozo", 0) and not parsed.entries:
            warnings.append("parse_error")
        if not parsed.entries:
            warnings.append("empty_feed")

        items: list[Raw] = []
        fetched = 0
        for entry in parsed.entries:
            fetched += 1
            guid = entry.get("id") or entry.get("link")
            if not guid or guid in seen:
                continue
            seen.add(guid)
            cursor.remember(guid)
            items.append(dict(entry))
            if request.limit is not None and len(items) >= request.limit:
                break

        cursor.etag = getattr(parsed, "etag", cursor.etag)
        stats = FetchStats(fetched=fetched, new=len(items), skipped=fetched - len(items))
        return FetchResult(
            items=items,
            state=cursor.to_state(),
            has_more=False,
            warnings=warnings,
            stats=stats,
        )

    def normalize(self, source: dict, raw: Raw) -> Document:
        url = raw.get("link") or raw.get("id") or ""
        canonical = canonicalize_url(url)
        published = _parse_date(raw)
        body, body_is_complete = _extract_body(raw)
        config = source.get("config") or {}
        metadata: dict = {"raw_keys": sorted(raw.keys())}
        if published is None:
            metadata["dateless"] = True

        return Document(
            id=sha256(f"{source.get('id')}:{canonical}".encode()).hexdigest(),
            tenant_id=str(source["tenant_id"]),
            source_id=str(source["id"]) if source.get("id") else "",
            source_type="rss",
            url=url,
            canonical_url=canonical,
            external_id=raw.get("id") or url,
            title=(raw.get("title") or "").strip(),
            body=body,
            summary=raw.get("summary"),
            language=raw.get("language") or config.get("language"),
            author=raw.get("author"),
            tags=[t.get("term", "") for t in raw.get("tags", []) if t.get("term")],
            media=_extract_media(raw),
            published_at=published,
            fetched_at=datetime.now(UTC),
            content_hash=content_hash(body),
            body_is_complete=body_is_complete,
            metadata=metadata,
        )


def _parse_date(raw: Raw) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = raw.get(key)
        if t:
            return datetime(*t[:6], tzinfo=UTC)
    return None


def _extract_body(raw: Raw) -> tuple[str, bool]:
    content = raw.get("content")
    if content and isinstance(content, list):
        value = content[0].get("value", "") or ""
        return value, len(value) >= _FULL_BODY_MIN
    return raw.get("summary", "") or "", False


def _extract_media(raw: Raw) -> list[str]:
    media: list[str] = []
    for m in raw.get("media_content", []) or []:
        if m.get("url"):
            media.append(m["url"])
    return media
