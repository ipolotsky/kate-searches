"""Стадия скоринга: новость -> RelevanceScore по критериям тенанта.

Использует дешёвую модель (settings.llm_model_score) через LLM-обёртку.
Промпт строится из brand_profile (см. docs/05_ai_pipeline_prompts.md).
"""

import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Tenant
from app.db.repositories import ArticleRepository, BrandProfileRepository
from app.llm.client import structured_completion
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


def score_article_run(session: Session, article_id: uuid.UUID, run_id: uuid.UUID) -> dict:
    """Оценить статью: extracted -> scored|filtered_out, записать relevance/relevance_score.

    Загружает brand_profile тенанта. Идемпотентно: guard по статусу 'extracted'.
    Без brand_profile тенанта скоринг пропускается.
    """
    article = ArticleRepository.get(session, article_id)
    if article is None or article.status != "extracted":
        return {"article_id": str(article_id), "status": "skipped"}

    profile_row = BrandProfileRepository.get_by_tenant(session, article.tenant_id)
    if profile_row is None:
        return {"article_id": str(article_id), "status": "skipped", "reason": "no_brand_profile"}

    tenant = session.get(Tenant, article.tenant_id)
    profile = {
        "company_name": tenant.name if tenant is not None else "",
        "company_description": profile_row.company_description or "",
        "audience_description": profile_row.audience_description or "",
        "filter_criteria": profile_row.filter_criteria or "",
        "criteria_weights": profile_row.criteria_weights or {},
    }
    score = score_article(article, profile, str(article.tenant_id), pipeline_run_id=run_id)
    passed = score.passes_threshold and score.overall_score >= profile_row.score_threshold
    ArticleRepository.advance_scored(
        session,
        article_id,
        relevance=score.model_dump(),
        relevance_score=score.overall_score,
        passed=passed,
    )
    return {
        "article_id": str(article_id),
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
