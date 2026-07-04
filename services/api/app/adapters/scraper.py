"""Scraper-адаптер: одностраничный fetch через CascadeFetcher + trafilatura-extract.

fetch использует только бесплатные fetcher-ы (httpx/crawl4ai). Если тело тонкое/заблокировано,
body_is_complete=False, и платную эскалацию (Firecrawl) с учётом COGS делает стадия extract —
так весь платный скрапинг проходит через ai_usage, а не теряется в адаптере.
"""

from datetime import UTC, datetime
from hashlib import sha256

from pydantic import BaseModel

from app.adapters.base import (
    AdapterCapabilities,
    BaseAdapter,
    FetchRequest,
    FetchResult,
    FetchStats,
    Raw,
)
from app.adapters.registry import AdapterRegistry
from app.config import settings
from app.fetch import CascadeFetcher
from app.fetch.base import is_usable
from app.models import Document
from app.pipeline.dedup import canonicalize_url, content_hash


class ScraperConfig(BaseModel):
    render_js: bool = False
    language: str | None = None
    novelty_days: int = 0


@AdapterRegistry.register
class ScraperAdapter(BaseAdapter):
    type = "scraper"
    capabilities = AdapterCapabilities(
        cursor_kind="none",
        supports_incremental=False,
        supports_backfill=False,
        provides_full_text=True,
        needs_javascript=False,
        respects_robots=True,
        emits_media=False,
        default_rate_limit_rpm=20,
    )
    config_model = ScraperConfig

    def fetch(self, request: FetchRequest) -> FetchResult:
        config = self.validate_config(request.source.get("config") or {})
        url = request.source["url"]
        # Только бесплатные fetcher-ы: платную эскалацию (Firecrawl) с учётом COGS в ai_usage
        # делает стадия extract, иначе стоимость теряется в адаптере (невосстановимо).
        fetcher = CascadeFetcher(allow_paid=False)
        page = fetcher.fetch_html(url, render_js=config.render_js)

        warnings: list[str] = []
        if page.error or not page.html:
            warnings.append(page.error or "empty_page")
            return FetchResult(
                items=[],
                state=request.state,
                warnings=warnings,
                stats=FetchStats(fetched=0, new=0, skipped=0),
            )

        raw: Raw = {
            "url": page.final_url or url,
            "html": page.html,
            "usable": is_usable(page, settings.extract_body_min_chars),
        }
        return FetchResult(
            items=[raw],
            state=request.state,
            has_more=False,
            warnings=warnings,
            stats=FetchStats(fetched=1, new=1, skipped=0),
        )

    def normalize(self, source: dict, raw: Raw) -> Document:
        url = raw.get("url") or source.get("url") or ""
        canonical = canonicalize_url(url)
        html = raw.get("html") or ""
        body, fields = _extract(html)
        config = source.get("config") or {}
        published = _parse_date(fields.get("date"))
        body_is_complete = bool(raw.get("usable")) and len(body) >= settings.extract_body_min_chars

        metadata: dict = {"scraper": True}
        if published is None:
            metadata["dateless"] = True

        return Document(
            id=sha256(f"{source.get('id')}:{canonical}".encode()).hexdigest(),
            tenant_id=str(source["tenant_id"]),
            source_id=str(source["id"]) if source.get("id") else "",
            source_type="scraper",
            url=url,
            canonical_url=canonical,
            external_id=canonical,
            title=(fields.get("title") or "").strip(),
            body=body,
            summary=fields.get("description"),
            language=fields.get("language") or config.get("language"),
            author=fields.get("author"),
            published_at=published,
            fetched_at=datetime.now(UTC),
            content_hash=content_hash(body),
            body_is_complete=body_is_complete,
            metadata=metadata,
        )


def _extract(html: str) -> tuple[str, dict]:
    if not html:
        return "", {}
    import trafilatura

    body = (
        trafilatura.extract(
            html,
            output_format="markdown",
            favor_precision=True,
            include_tables=True,
            include_comments=False,
        )
        or ""
    )
    fields: dict = {}
    try:
        meta = trafilatura.extract_metadata(html)
        if meta is not None:
            for key in ("title", "author", "date", "language", "description"):
                fields[key] = getattr(meta, key, None)
    except Exception:
        fields = {}
    return body, fields


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(str(value)[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed
