"""Стадия генерации: прошедшая отбор новость -> DraftPost в голосе бренда -> строка posts.

Использует сильную модель (settings.llm_model_draft). Few-shot из brand_profile.voice_examples
(см. docs/05_ai_pipeline_prompts.md §4). Запускается отдельным потоком (on-demand), не в дневном
прогоне: LLM-вызов вынесен между двумя короткими транзакциями (сильная модель держит ~20-60с).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.config import settings
from app.db.engine import session_scope
from app.db.models import Tenant
from app.db.repositories import ArticleRepository, BrandProfileRepository, PostRepository
from app.llm.client import SessionFactory, structured_completion_with_usage
from app.models import DraftPost, RelevanceScore

SYSTEM_TEMPLATE = """Ты пишешь черновик статьи/поста для бренда {company} в его фирменном голосе.
{company_description}
Аудитория бренда: {audience}.

Голос и тон: {voice_config}
Следуй стилю этих реальных постов бренда (few-shot). У каждого примера указан инфоповод-источник,
из которого он родился — учись связке «инфоповод → пост»:
{voice_examples}

Задача: на основе новости написать материал-симбиоз «инфоповод × бренд».
Это НЕ пересказ новости. Органично вплети инфоповод в бренд — его позиционирование,
экспертизу и угол ({unique_angle}) — и добавь собственную ценность для аудитории.
В поле brand_tie_in объясни угол симбиоза: почему этот инфоповод работает на этот бренд.

Требования SEO/AEO (обязательно): answer-first (40-60 слов в начале каждой секции),
иерархия H1/H2/H3, короткие абзацы/списки, секция FAQ с реальными вопросами,
явные сущности, JSON-LD (Article + FAQPage), строго совпадающий с видимым текстом.
Язык черновика: {language}."""


class GeneratableDocument(Protocol):
    """Минимум полей для генерации — совместим и с Document (pydantic), и с Article (ORM)."""

    title: str | None
    url: str
    published_at: datetime | None
    body: str | None


@dataclass(frozen=True)
class _DocSnapshot:
    """Снимок полей статьи для промпта — отвязан от ORM-сессии (LLM зовём вне транзакции)."""

    title: str | None
    url: str
    published_at: datetime | None
    body: str | None


def build_messages(
    doc: GeneratableDocument, score: RelevanceScore, profile: dict, language: str
) -> list[dict]:
    system = SYSTEM_TEMPLATE.format(
        company=profile.get("company_name", ""),
        company_description=profile.get("company_description", ""),
        audience=profile.get("audience_description", ""),
        voice_config=_format_voice_config(profile.get("voice_config", {})),
        voice_examples=_format_examples(profile.get("voice_examples", [])),
        unique_angle=profile.get("unique_angle_hint", "ресейл/архив/винтаж/редкость/стоимость"),
        language=language,
    )
    published_at = doc.published_at.isoformat() if doc.published_at is not None else "неизвестна"
    user = (
        f"Новость: «{doc.title}» ({doc.url}), дата {published_at}.\n"
        f"Почему берём: {score.decision_summary}\n"
        f"Тренд: {score.trend_explanation}\n\n"
        f"Текст новости:\n{doc.body}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def generate_draft(
    doc: GeneratableDocument,
    score: RelevanceScore,
    profile: dict,
    tenant_id: str,
    language: str = "en",
    *,
    pipeline_run_id: uuid.UUID | str | None = None,
) -> tuple[DraftPost, float]:
    return structured_completion_with_usage(
        model=settings.llm_model_draft,
        messages=build_messages(doc, score, profile, language),
        response_model=DraftPost,
        tenant_id=tenant_id,
        stage="draft",
        pipeline_run_id=pipeline_run_id,
        max_tokens=settings.llm_draft_max_tokens,
    )


def generate_draft_run(
    article_id: uuid.UUID | str,
    *,
    session_factory: SessionFactory = session_scope,
) -> dict:
    """Сгенерировать черновик для прошедшей отбор статьи: scored -> drafting -> drafted + posts.

    Идемпотентно и безопасно к конкуренции: атомарный claim scored -> drafting ДО LLM-вызова, так
    что два конкурентных воркера не дублируют спенд сильной модели. При сбое LLM claim откатывается
    (drafting -> scored), статья снова доступна. Без brand_profile тенанта генерация пропускается.
    Стоимость пишется в posts.ai_cost_usd и в ai_usage(stage='draft').
    """
    article_uuid = article_id if isinstance(article_id, uuid.UUID) else uuid.UUID(str(article_id))

    with session_factory() as session:
        article = ArticleRepository.get(session, article_uuid)
        if article is None or article.status != "scored":
            return {"article_id": str(article_uuid), "status": "skipped"}
        if article.relevance is None:
            return {"article_id": str(article_uuid), "status": "skipped", "reason": "no_relevance"}
        profile_row = BrandProfileRepository.get_by_tenant(session, article.tenant_id)
        if profile_row is None:
            return {
                "article_id": str(article_uuid),
                "status": "skipped",
                "reason": "no_brand_profile",
            }
        tenant = session.get(Tenant, article.tenant_id)
        voice_config = profile_row.voice_config or {}
        profile: dict = {
            "company_name": tenant.name if tenant is not None else "",
            "company_description": profile_row.company_description or "",
            "audience_description": profile_row.audience_description or "",
            "voice_config": voice_config,
            "voice_examples": profile_row.voice_examples or [],
        }
        angle = voice_config.get("unique_angle_hint")
        if angle:
            profile["unique_angle_hint"] = angle
        language = _pick_language(profile_row, tenant, article)
        score = RelevanceScore(**article.relevance)
        doc = _DocSnapshot(
            title=article.title,
            url=article.url,
            published_at=article.published_at,
            body=article.body,
        )
        tenant_id = str(article.tenant_id)
        run_id = article.last_pipeline_run_id
        # claim последним в tx: проигравший конкурент получит rowcount=0 и не пойдёт в LLM
        if not ArticleRepository.claim_for_draft(session, article_uuid):
            return {
                "article_id": str(article_uuid),
                "status": "skipped",
                "reason": "already_claimed",
            }

    try:
        draft, cost = generate_draft(
            doc, score, profile, tenant_id, language, pipeline_run_id=run_id
        )
    except Exception:
        with session_factory() as session:
            ArticleRepository.release_draft_claim(session, article_uuid)
        raise

    with session_factory() as session:
        advanced = ArticleRepository.advance_drafted(session, article_uuid)
        if not advanced:
            return {"article_id": str(article_uuid), "status": "skipped", "reason": "not_claimed"}
        post_id = PostRepository.create_from_draft(
            session,
            tenant_id=uuid.UUID(tenant_id),
            article_id=article_uuid,
            draft=draft,
            language=language,
            ai_model=settings.llm_model_draft,
            ai_cost_usd=cost,
        )
    return {
        "article_id": str(article_uuid),
        "status": "drafted",
        "post_id": str(post_id),
        "run_id": str(run_id) if run_id is not None else None,
    }


def _pick_language(profile_row, tenant, article) -> str:
    locales = profile_row.locales or []
    if locales:
        return locales[0]
    if tenant is not None and tenant.default_locale:
        return tenant.default_locale
    if article.language:
        return article.language
    return "en"


def _format_voice_config(voice_config: object) -> str:
    """Рендерит голос/тон читаемым текстом (не Python-repr словаря). unique_angle_hint исключён —
    он подставляется отдельно в {unique_angle}, иначе задвоился бы в промпте."""
    if not isinstance(voice_config, dict):
        return str(voice_config or "")
    parts = [
        str(value) for key, value in voice_config.items() if key != "unique_angle_hint" and value
    ]
    return " ".join(parts)


def _format_examples(examples: list) -> str:
    """Форматирует few-shot голоса бренда, кап 3 (спека §4.2). Показывает инфоповод-источник."""
    if not examples:
        return "Примеров пока нет — следуй голосу и тону выше."
    blocks: list[str] = []
    for example in examples[:3]:
        if not isinstance(example, dict):
            blocks.append(f"Пост: {example}")
            continue
        lines: list[str] = []
        source_url = example.get("source_url")
        if source_url:
            lines.append(f"Инфоповод: {source_url}")
        text = example.get("post_text") or example.get("text") or ""
        lines.append(f"Пост: {text}")
        why = example.get("why")
        if why:
            lines.append(f"(почему хорош: {why})")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
