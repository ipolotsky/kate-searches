"""Стадия extract: гидратация тела -> markdown, язык, пересчёт хешей, new -> extracted.

Не-LLM стадия. Гидратирует только когда тело неполное/тонкое (body_is_complete читается
из articles.metadata). Каждый платный fetch (Firecrawl) пишет строку ai_usage(stage='extract').
"""

import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.db.repositories import ArticleRepository, insert_ai_usage
from app.pipeline.dedup import content_hash, simhash64, to_signed


def needs_hydration(body_is_complete: bool, body: str, min_chars: int) -> bool:
    return (not body_is_complete) or len(body or "") < min_chars


def extract_text(html: str) -> tuple[str, str | None]:
    """Чистое тело в markdown + язык через trafilatura. Пустой результат -> ("", None)."""
    if not html:
        return "", None
    import trafilatura

    text = trafilatura.extract(
        html,
        output_format="markdown",
        favor_precision=True,
        include_tables=True,
        include_comments=False,
    )
    language: str | None = None
    try:
        meta = trafilatura.extract_metadata(html)
        language = getattr(meta, "language", None) if meta is not None else None
    except Exception:
        language = None
    return (text or ""), language


def _render_js_for_source(source_type: str | None) -> bool:
    if not source_type:
        return False
    from app.adapters import REGISTRY

    if source_type not in REGISTRY:
        return False
    return bool(REGISTRY[source_type].capabilities.needs_javascript)


def extract_article(
    session: Session,
    article_id: uuid.UUID,
    *,
    fetcher=None,
    pipeline_run_id: uuid.UUID | None = None,
) -> dict:
    """Гидратировать статью и перевести new -> extracted. Идемпотентно (guard по статусу)."""
    article = ArticleRepository.get(session, article_id)
    if article is None or article.status != "new":
        return {"article_id": str(article_id), "status": "skipped"}

    metadata = dict(article.doc_metadata or {})
    body_is_complete = bool(metadata.get("body_is_complete"))
    current_body = article.body or ""
    min_chars = settings.extract_body_min_chars

    final_body = current_body
    language = article.language
    media = None
    extraction_failed = False
    cost_usd = 0.0
    fetcher_name = None

    if needs_hydration(body_is_complete, current_body, min_chars):
        if fetcher is None:
            from app.fetch import CascadeFetcher

            fetcher = CascadeFetcher(allow_paid=True)
        render_js = _render_js_for_source(_source_type(session, article))
        page = fetcher.fetch_html(article.url, render_js=render_js)
        cost_usd = page.cost_usd
        fetcher_name = page.fetcher
        if page.error or not page.html:
            extraction_failed = True
        else:
            extracted, detected_language = extract_text(page.html)
            if extracted.strip():
                final_body = extracted
                if detected_language:
                    language = detected_language
            else:
                extraction_failed = True

    if cost_usd > 0:
        insert_ai_usage(
            session,
            tenant_id=article.tenant_id,
            user_id=None,
            stage="extract",
            model=fetcher_name,
            input_tokens=None,
            output_tokens=None,
            cost_usd=cost_usd,
            request_id=None,
            pipeline_run_id=pipeline_run_id,
        )

    new_hash = content_hash(final_body)
    new_simhash = to_signed(simhash64(final_body))
    improved = final_body != current_body or not extraction_failed

    if extraction_failed and not improved:
        ArticleRepository.flag_extraction_failed(
            session,
            article_id,
            simhash_signed=new_simhash,
            content_hash_value=new_hash,
            metadata_patch={"extraction_failed": True},
        )
        return {"article_id": str(article_id), "status": "new", "extraction_failed": True}

    patch: dict = {}
    if extraction_failed:
        patch["extraction_failed"] = True
    advanced = ArticleRepository.advance_extracted(
        session,
        article_id,
        body=final_body,
        content_hash_value=new_hash,
        simhash_signed=new_simhash,
        language=language,
        media=media,
        metadata_patch=patch,
    )
    return {
        "article_id": str(article_id),
        "status": "extracted" if advanced else "skipped",
        "cost_usd": cost_usd,
    }


def _source_type(session: Session, article) -> str | None:
    from app.db.repositories import SourceRepository

    if article.source_id is None:
        return None
    source = SourceRepository.get(session, article.source_id)
    return source.type if source is not None else None
