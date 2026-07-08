"""Стадия скоринга: новость -> RelevanceScore по критериям тенанта.

Использует дешёвую модель (settings.llm_model_score) через LLM-обёртку.
Промпт строится из brand_profile (см. docs/05_ai_pipeline_prompts.md).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.config import settings
from app.db.engine import session_scope
from app.db.models import Tenant
from app.db.repositories import ArticleRepository, BrandProfileRepository
from app.llm.client import SessionFactory, structured_completion
from app.models import RelevanceScore

SYSTEM_TEMPLATE = """Ты — главный редактор и маркетинг-директор бренда {company}.
{company_description}
Твоя аудитория: {audience}.

Критерии отбора этого бренда (что берём, что отбрасываем):
{filter_criteria}

{criteria_weights}

Оцени новость по каждому критерию (low/medium/high) с обоснованием ПЕРЕД баллом,
затем дай итоговый скор 0-100, приоритет HOT/WARM/COLD/DROP и решение.
Бренду интересны инфоповоды, после которых аудитория может захотеть найти, купить,
продать, обсудить или переоценить вещь из новости.

Будь строгим и не завышай оценки. Ставь high только при явно сильном сигнале по критерию;
при сомнении выбирай medium или low. Большинство новостей для этого бренда проходные — их место
COLD или DROP. Приоритет HOT только для прямого сильного попадания в критерии, по которым бренд
берёт контент. Если новость не связана напрямую с тем, что берёт бренд (см. критерии отбора выше),
ставь DROP, насколько бы заметной она ни была в моде. Итоговый скор отражает взвешенную важность
критериев для бренда, а не общую громкость новости."""


class ScorableDocument(Protocol):
    """Минимум полей для скоринга — совместим и с Document (pydantic), и с Article (ORM)."""

    title: str | None
    body: str | None
    url: str
    published_at: datetime | None


@dataclass(frozen=True)
class _DocSnapshot:
    """Снимок полей статьи для промпта — отвязан от ORM-сессии (LLM зовём вне транзакции)."""

    title: str | None
    body: str | None
    url: str
    published_at: datetime | None


def score_article_run(
    article_id: uuid.UUID | str,
    run_id: uuid.UUID | str | None,
    *,
    session_factory: SessionFactory = session_scope,
) -> dict:
    """Оценить статью: extracted -> scoring -> scored|filtered_out, записать relevance/score.

    Идемпотентно и безопасно к конкуренции: атомарный claim extracted -> scoring ДО LLM-вызова
    (коммитится своей транзакцией), так что конкурентные прогоны одного run_id не скорят статью
    дважды. При сбое LLM claim откатывается (scoring -> extracted), статья снова доступна.
    Без brand_profile тенанта скоринг пропускается.
    """
    article_uuid = article_id if isinstance(article_id, uuid.UUID) else uuid.UUID(str(article_id))

    with session_factory() as session:
        article = ArticleRepository.get(session, article_uuid)
        if article is None or article.status != "extracted":
            return {"article_id": str(article_uuid), "status": "skipped"}
        profile_row = BrandProfileRepository.get_by_tenant(session, article.tenant_id)
        if profile_row is None:
            return {
                "article_id": str(article_uuid),
                "status": "skipped",
                "reason": "no_brand_profile",
            }
        tenant = session.get(Tenant, article.tenant_id)
        profile = {
            "company_name": tenant.name if tenant is not None else "",
            "company_description": profile_row.company_description or "",
            "audience_description": profile_row.audience_description or "",
            "filter_criteria": profile_row.filter_criteria or "",
            "criteria_weights": profile_row.criteria_weights or {},
        }
        threshold = profile_row.score_threshold
        doc = _DocSnapshot(
            title=article.title,
            body=article.body,
            url=article.url,
            published_at=article.published_at,
        )
        tenant_id = str(article.tenant_id)
        # claim последним в tx: проигравший конкурент получит rowcount=0 и не пойдёт в LLM
        if not ArticleRepository.claim_for_scoring(session, article_uuid):
            return {
                "article_id": str(article_uuid),
                "status": "skipped",
                "reason": "already_claimed",
            }

    try:
        score = score_article(doc, profile, tenant_id, pipeline_run_id=run_id)
    except Exception:
        with session_factory() as session:
            ArticleRepository.release_scoring_claim(session, article_uuid)
        raise

    passed = score.passes_threshold and score.overall_score >= threshold
    with session_factory() as session:
        advanced = ArticleRepository.advance_scored(
            session,
            article_uuid,
            relevance=score.model_dump(),
            relevance_score=score.overall_score,
            passed=passed,
        )
        if not advanced:
            return {"article_id": str(article_uuid), "status": "skipped", "reason": "not_claimed"}
    return {
        "article_id": str(article_uuid),
        "status": "scored" if passed else "filtered_out",
        "overall_score": score.overall_score,
    }


def score_article(
    doc: ScorableDocument,
    profile: dict,
    tenant_id: str,
    *,
    pipeline_run_id: uuid.UUID | str | None = None,
) -> RelevanceScore:
    return structured_completion(
        model=settings.llm_model_score,
        messages=build_messages(doc, profile),
        response_model=RelevanceScore,
        tenant_id=tenant_id,
        stage="score",
        pipeline_run_id=pipeline_run_id,
    )


def build_messages(doc: ScorableDocument, profile: dict) -> list[dict]:
    system = SYSTEM_TEMPLATE.format(
        company=profile.get("company_name", ""),
        company_description=profile.get("company_description", ""),
        audience=profile.get("audience_description", ""),
        filter_criteria=profile.get("filter_criteria", ""),
        criteria_weights=_format_weights(profile.get("criteria_weights") or {}),
    )
    published_at = doc.published_at.isoformat() if doc.published_at is not None else "неизвестна"
    user = (
        f"Заголовок: {doc.title}\nДата: {published_at}\nИсточник: {doc.url}\n\nТекст:\n{doc.body}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _format_weights(weights: dict) -> str:
    if not weights:
        return "Веса критериев: все критерии равнозначны."
    lines = [f"- {name}: {value}" for name, value in weights.items()]
    body = "\n".join(lines)
    return (
        "Веса критериев этого бренда (чем выше вес — тем важнее критерий "
        "для итогового скора):\n" + body
    )
