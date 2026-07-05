"""Репозитории записи/чтения под service_role (обход RLS).

tenant_id всегда берётся из строки sources, не из сырья адаптера (защита от кросс-тенант
записи под bypassrls). Веб-чтения идут отдельно под authenticated со скоупом RLS.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import cast, func, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import AiUsage, Article, ArticleSource, BrandProfile, PipelineRun, Post, Source
from app.models import Document, DraftPost

_LIVE_STATUSES = ("new", "extracted")


def insert_ai_usage(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    stage: str,
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_usd: float,
    request_id: str | None,
    pipeline_run_id: uuid.UUID | None = None,
) -> AiUsage:
    row = AiUsage(
        tenant_id=tenant_id,
        user_id=user_id,
        stage=stage,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        request_id=request_id,
        pipeline_run_id=pipeline_run_id,
    )
    session.add(row)
    session.flush()
    return row


class ArticleRepository:
    """URL-слой дедупа (upsert on conflict) + контент-слой (hash/simhash) + провенанс."""

    @staticmethod
    def upsert_document(
        session: Session, doc: Document, *, pipeline_run_id: uuid.UUID | None = None
    ) -> tuple[uuid.UUID | None, bool]:
        """Вставить статью по (tenant_id, canonical_url). id — новая строка, None — дубль по URL."""
        metadata = {**doc.metadata, "body_is_complete": doc.body_is_complete}
        stmt = (
            pg_insert(Article)
            .values(
                tenant_id=uuid.UUID(str(doc.tenant_id)),
                source_id=uuid.UUID(str(doc.source_id)) if doc.source_id else None,
                url=doc.url,
                canonical_url=doc.canonical_url,
                external_id=doc.external_id,
                title=doc.title,
                body=doc.body,
                summary=doc.summary,
                language=doc.language,
                author=doc.author,
                tags=doc.tags,
                media=doc.media,
                published_at=doc.published_at,
                fetched_at=doc.fetched_at,
                content_hash=doc.content_hash,
                status="new",
                doc_metadata=metadata,
                last_pipeline_run_id=pipeline_run_id,
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "canonical_url"])
            .returning(Article.id)
        )
        row = session.execute(stmt).first()
        if row is None:
            return None, False
        return row[0], True

    @staticmethod
    def get(session: Session, article_id: uuid.UUID) -> Article | None:
        return session.get(Article, article_id)

    @staticmethod
    def find_by_content_hash(
        session: Session,
        tenant_id: uuid.UUID,
        content_hash: str | None,
        *,
        exclude_id: uuid.UUID | None = None,
        statuses: tuple[str, ...] = _LIVE_STATUSES,
    ) -> list[Article]:
        if not content_hash:
            return []
        query = (
            select(Article)
            .where(
                Article.tenant_id == tenant_id,
                Article.content_hash == content_hash,
                Article.status.in_(statuses),
            )
            .order_by(Article.created_at, Article.id)
        )
        if exclude_id is not None:
            query = query.where(Article.id != exclude_id)
        return list(session.execute(query).scalars())

    @staticmethod
    def find_id_by_canonical(
        session: Session, tenant_id: uuid.UUID, canonical_url: str
    ) -> uuid.UUID | None:
        return session.execute(
            select(Article.id).where(
                Article.tenant_id == tenant_id, Article.canonical_url == canonical_url
            )
        ).scalar_one_or_none()

    @staticmethod
    def run_articles(
        session: Session,
        run_id: uuid.UUID,
        *,
        statuses: tuple[str, ...] = _LIVE_STATUSES,
    ) -> list[Article]:
        return list(
            session.execute(
                select(Article)
                .where(Article.last_pipeline_run_id == run_id, Article.status.in_(statuses))
                .order_by(Article.created_at, Article.id)
            ).scalars()
        )

    @staticmethod
    def scored_articles(
        session: Session,
        tenant_id: uuid.UUID,
        *,
        article_ids: list[uuid.UUID] | None = None,
    ) -> list[Article]:
        """Прошедшие отбор статьи тенанта (status='scored') — кандидаты на генерацию черновика."""
        query = (
            select(Article)
            .where(Article.tenant_id == tenant_id, Article.status == "scored")
            .order_by(Article.created_at, Article.id)
        )
        if article_ids is not None:
            query = query.where(Article.id.in_(article_ids))
        return list(session.execute(query).scalars())

    @staticmethod
    def run_counters(session: Session, run_id: uuid.UUID) -> dict:
        rows = session.execute(
            select(Article.status, func.count())
            .where(Article.last_pipeline_run_id == run_id)
            .group_by(Article.status)
        )
        by_status = {row[0]: row[1] for row in rows}
        inserted = sum(by_status.values())
        return {
            "fetched": inserted,
            "new": inserted,
            "extracted": by_status.get("extracted", 0),
            "scored": by_status.get("scored", 0),
            "filtered_out": by_status.get("filtered_out", 0),
            "drafted": by_status.get("drafted", 0),
            "duplicated": by_status.get("duplicate", 0),
            "failed": by_status.get("new", 0),
        }

    @staticmethod
    def window_candidates(
        session: Session,
        tenant_id: uuid.UUID,
        *,
        since: datetime | None,
        statuses: tuple[str, ...] = _LIVE_STATUSES,
    ) -> list[Article]:
        """Кандидаты для near-dup скана: статьи тенанта в дневном окне с непустым simhash."""
        query = (
            select(Article)
            .where(
                Article.tenant_id == tenant_id,
                Article.simhash.is_not(None),
                Article.status.in_(statuses),
            )
            .order_by(Article.created_at, Article.id)
        )
        if since is not None:
            query = query.where(Article.published_at >= since)
        return list(session.execute(query).scalars())

    @staticmethod
    def mark_duplicate(
        session: Session,
        article_id: uuid.UUID,
        *,
        duplicate_of: uuid.UUID,
        method: str,
        distance: int | None = None,
    ) -> bool:
        """Пометить дублем. Guard: только статус new/extracted (каноничность заморожена)."""
        provenance = {
            "dedup_method": method,
            "matched_article_id": str(duplicate_of),
            "distance": distance,
        }
        stmt = (
            update(Article)
            .where(Article.id == article_id, Article.status.in_(_LIVE_STATUSES))
            .values(
                status="duplicate",
                duplicate_of=duplicate_of,
                doc_metadata=Article.doc_metadata.op("||")(cast(provenance, JSONB)),
            )
        )
        result = session.execute(stmt)
        return bool(result.rowcount)

    @staticmethod
    def set_simhash(session: Session, article_id: uuid.UUID, simhash_signed: int | None) -> None:
        session.execute(
            update(Article).where(Article.id == article_id).values(simhash=simhash_signed)
        )

    @staticmethod
    def advance_extracted(
        session: Session,
        article_id: uuid.UUID,
        *,
        body: str,
        content_hash_value: str,
        simhash_signed: int | None,
        language: str | None,
        media: list | None,
        metadata_patch: dict,
    ) -> bool:
        """new -> extracted (guard WHERE status='new', идемпотентно)."""
        values: dict = {
            "status": "extracted",
            "body": body,
            "content_hash": content_hash_value,
            "simhash": simhash_signed,
            "doc_metadata": Article.doc_metadata.op("||")(cast(metadata_patch, JSONB)),
        }
        if language is not None:
            values["language"] = language
        if media is not None:
            values["media"] = media
        stmt = (
            update(Article)
            .where(Article.id == article_id, Article.status == "new")
            .values(**values)
        )
        return bool(session.execute(stmt).rowcount)

    @staticmethod
    def flag_extraction_failed(
        session: Session,
        article_id: uuid.UUID,
        *,
        simhash_signed: int | None,
        content_hash_value: str,
        metadata_patch: dict,
    ) -> None:
        """Провал гидратации: статус остаётся new (строку не теряем), метим для наблюдаемости."""
        session.execute(
            update(Article)
            .where(Article.id == article_id, Article.status == "new")
            .values(
                simhash=simhash_signed,
                content_hash=content_hash_value,
                doc_metadata=Article.doc_metadata.op("||")(cast(metadata_patch, JSONB)),
            )
        )

    @staticmethod
    def advance_scored(
        session: Session,
        article_id: uuid.UUID,
        *,
        relevance: dict,
        relevance_score: int,
        passed: bool,
    ) -> bool:
        """extracted -> scored|filtered_out (guard WHERE status='extracted', идемпотентно)."""
        stmt = (
            update(Article)
            .where(Article.id == article_id, Article.status == "extracted")
            .values(
                status="scored" if passed else "filtered_out",
                relevance=relevance,
                relevance_score=relevance_score,
            )
        )
        return bool(session.execute(stmt).rowcount)

    @staticmethod
    def claim_for_draft(session: Session, article_id: uuid.UUID) -> bool:
        """Атомарный claim scored -> drafting ДО LLM-вызова (guard от конкурентного double-spend).

        Ровно один конкурентный воркер получает rowcount=1; проигравший видит status!='scored'.
        """
        stmt = (
            update(Article)
            .where(Article.id == article_id, Article.status == "scored")
            .values(status="drafting")
        )
        return bool(session.execute(stmt).rowcount)

    @staticmethod
    def advance_drafted(session: Session, article_id: uuid.UUID) -> bool:
        """drafting -> drafted (guard WHERE status='drafting', идемпотентно)."""
        stmt = (
            update(Article)
            .where(Article.id == article_id, Article.status == "drafting")
            .values(status="drafted")
        )
        return bool(session.execute(stmt).rowcount)

    @staticmethod
    def release_draft_claim(session: Session, article_id: uuid.UUID) -> bool:
        """Откат drafting -> scored при сбое генерации (статья снова доступна для повтора)."""
        stmt = (
            update(Article)
            .where(Article.id == article_id, Article.status == "drafting")
            .values(status="scored")
        )
        return bool(session.execute(stmt).rowcount)

    @staticmethod
    def upsert_article_source(
        session: Session,
        *,
        tenant_id: uuid.UUID,
        article_id: uuid.UUID,
        source_id: uuid.UUID | None,
        external_id: str | None,
        priority_at_seen: int | None,
    ) -> None:
        stmt = (
            pg_insert(ArticleSource)
            .values(
                tenant_id=tenant_id,
                article_id=article_id,
                source_id=source_id,
                external_id=external_id,
                priority_at_seen=priority_at_seen,
            )
            .on_conflict_do_nothing(index_elements=["article_id", "source_id"])
        )
        session.execute(stmt)


class PostRepository:
    """Персист черновиков: DraftPost -> строка posts (тело + AEO-разметка + атрибуция стоимости)."""

    @staticmethod
    def create_from_draft(
        session: Session,
        *,
        tenant_id: uuid.UUID,
        article_id: uuid.UUID,
        draft: DraftPost,
        language: str,
        ai_model: str,
        ai_cost_usd: float | None,
    ) -> uuid.UUID:
        seo = {
            "meta_description": draft.meta_description,
            "keywords": draft.keywords,
            "entities": draft.entities,
            "brand_tie_in": draft.brand_tie_in,
            "seo_instructions": draft.seo_instructions,
        }
        post = Post(
            tenant_id=tenant_id,
            article_id=article_id,
            title=draft.title,
            body_markdown=draft.body_markdown,
            faq=[item.model_dump() for item in draft.faq],
            json_ld=draft.json_ld,
            seo=seo,
            suggested_titles=draft.suggested_titles,
            language=language,
            ai_model=ai_model,
            ai_cost_usd=ai_cost_usd,
        )
        session.add(post)
        session.flush()
        return post.id


class SourceRepository:
    @staticmethod
    def get_due_sources(
        session: Session, tenant_id: uuid.UUID, *, now: datetime | None = None
    ) -> list[Source]:
        query = select(Source).where(Source.tenant_id == tenant_id, Source.enabled.is_(True))
        if now is not None:
            query = query.where((Source.next_run_at.is_(None)) | (Source.next_run_at <= now))
        return list(session.execute(query).scalars())

    @staticmethod
    def get(session: Session, source_id: uuid.UUID) -> Source | None:
        return session.get(Source, source_id)

    @staticmethod
    def priority_map(session: Session, tenant_id: uuid.UUID) -> dict[uuid.UUID, int]:
        rows = session.execute(
            select(Source.id, Source.priority).where(Source.tenant_id == tenant_id)
        )
        return {row[0]: row[1] for row in rows}

    @staticmethod
    def advance_state(
        session: Session,
        source_id: uuid.UUID,
        *,
        new_state: dict,
        last_run_at: datetime,
        next_run_at: datetime | None = None,
    ) -> None:
        session.execute(
            update(Source)
            .where(Source.id == source_id)
            .values(
                state=new_state,
                last_run_at=last_run_at,
                next_run_at=next_run_at,
                last_status="ok",
                last_error=None,
            )
        )

    @staticmethod
    def set_health(
        session: Session,
        source_id: uuid.UUID,
        *,
        last_status: str,
        last_error: str | None = None,
        last_error_at: datetime | None = None,
    ) -> None:
        session.execute(
            update(Source)
            .where(Source.id == source_id)
            .values(
                last_status=last_status,
                last_error=last_error,
                last_error_at=last_error_at,
            )
        )


class BrandProfileRepository:
    @staticmethod
    def get_by_tenant(session: Session, tenant_id: uuid.UUID) -> BrandProfile | None:
        return session.execute(
            select(BrandProfile).where(BrandProfile.tenant_id == tenant_id)
        ).scalar_one_or_none()


class PipelineRunRepository:
    @staticmethod
    def claim_run(
        session: Session, *, tenant_id: uuid.UUID, run_date: date, mode: str = "incremental"
    ) -> uuid.UUID | None:
        """Атомарный claim дневного прогона. id значит вставку, None — прогон уже есть."""
        stmt = (
            pg_insert(PipelineRun)
            .values(tenant_id=tenant_id, run_date=run_date, mode=mode, status="running")
            .on_conflict_do_nothing(index_elements=["tenant_id", "run_date", "mode"])
            .returning(PipelineRun.id)
        )
        row = session.execute(stmt).first()
        return row[0] if row is not None else None

    @staticmethod
    def get(session: Session, run_id: uuid.UUID) -> PipelineRun | None:
        return session.get(PipelineRun, run_id)

    @staticmethod
    def stale_running(session: Session, *, before: datetime) -> list[PipelineRun]:
        """Прогоны, зависшие в running дольше порога (потерян enqueue / крэш воркера)."""
        return list(
            session.execute(
                select(PipelineRun).where(
                    PipelineRun.status == "running", PipelineRun.started_at < before
                )
            ).scalars()
        )

    @staticmethod
    def finalize(
        session: Session,
        run_id: uuid.UUID,
        *,
        counters: dict,
        status: str,
        stats: dict | None = None,
    ) -> None:
        session.execute(
            update(PipelineRun)
            .where(PipelineRun.id == run_id)
            .values(
                status=status,
                finished_at=func.now(),
                fetched=counters.get("fetched", 0),
                new=counters.get("new", 0),
                duplicated=counters.get("duplicated", 0),
                extracted=counters.get("extracted", 0),
                scored=counters.get("scored", 0),
                filtered_out=counters.get("filtered_out", 0),
                drafted=counters.get("drafted", 0),
                failed=counters.get("failed", 0),
                stats=stats or {},
            )
        )

    @staticmethod
    def refresh_drafted(session: Session, run_id: uuid.UUID) -> None:
        """Пересчитать ТОЛЬКО счётчик drafted по финальным статусам статей прогона.

        Генерация идёт отдельным потоком (on-demand) после финализации прогона, поэтому обновляем
        точечно, не трогая status/finished_at/прочие счётчики уже завершённого прогона.
        """
        drafted = (
            select(func.count())
            .select_from(Article)
            .where(Article.last_pipeline_run_id == run_id, Article.status == "drafted")
            .scalar_subquery()
        )
        session.execute(update(PipelineRun).where(PipelineRun.id == run_id).values(drafted=drafted))
