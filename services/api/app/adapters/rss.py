"""RSS/Atom адаптер.

GUID — ключ идентичности (fallback на link). pubDate — только для датирования.
state хранит множество уже виденных guid + ETag для условных запросов.
"""

from datetime import UTC, datetime
from hashlib import sha256

import feedparser

from app.adapters.base import Raw, State
from app.models import Document
from app.pipeline.dedup import canonicalize_url


class RssAdapter:
    type = "rss"

    def fetch(self, source: dict, state: State) -> tuple[list[Raw], State]:
        seen: set[str] = set(state.get("seen_guids", []))
        parsed = feedparser.parse(source["url"], etag=state.get("etag"))

        new_items: list[Raw] = []
        for entry in parsed.entries:
            guid = entry.get("id") or entry.get("link")
            if not guid or guid in seen:
                continue
            seen.add(guid)
            new_items.append(dict(entry))

        new_state: State = {
            "seen_guids": list(seen)[-5000:],  # ограничиваем рост
            "etag": getattr(parsed, "etag", state.get("etag")),
        }
        return new_items, new_state

    def normalize(self, source: dict, raw: Raw) -> Document:
        url = raw.get("link") or raw.get("id") or ""
        canonical = canonicalize_url(url)
        published = _parse_date(raw)
        body = _extract_body(raw)
        external_id = raw.get("id") or url

        return Document(
            id=sha256(f"{source['id']}:{canonical}".encode()).hexdigest(),
            tenant_id=str(source["tenant_id"]),
            source_id=str(source["id"]),
            source_type="rss",
            url=url,
            canonical_url=canonical,
            external_id=external_id,
            title=raw.get("title", "").strip(),
            body=body,
            summary=raw.get("summary"),
            language=raw.get("language") or source.get("config", {}).get("language"),
            author=raw.get("author"),
            tags=[t.get("term", "") for t in raw.get("tags", []) if t.get("term")],
            media=_extract_media(raw),
            published_at=published,
            fetched_at=datetime.now(UTC),
            content_hash=sha256(body.encode()).hexdigest(),
            metadata={"raw_keys": list(raw.keys())},
        )


def _parse_date(raw: Raw) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        t = raw.get(key)
        if t:
            return datetime(*t[:6], tzinfo=UTC)
    return datetime.now(UTC)


def _extract_body(raw: Raw) -> str:
    content = raw.get("content")
    if content and isinstance(content, list):
        return content[0].get("value", "")
    return raw.get("summary", "")


def _extract_media(raw: Raw) -> list[str]:
    media: list[str] = []
    for m in raw.get("media_content", []) or []:
        if m.get("url"):
            media.append(m["url"])
    return media
