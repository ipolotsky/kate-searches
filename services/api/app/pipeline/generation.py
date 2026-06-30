"""Стадия генерации: прошедшая отбор новость -> DraftPost в голосе бренда.

Использует сильную модель (settings.llm_model_draft).
Few-shot из brand_profile.voice_examples (см. docs/05_ai_pipeline_prompts.md).
"""

from app.config import settings
from app.llm.client import structured_completion
from app.models import Document, DraftPost, RelevanceScore

SYSTEM_TEMPLATE = """Ты пишешь черновик статьи/поста для бренда {company} в его фирменном голосе.

Голос и тон: {voice_config}
Следуй стилю этих реальных постов бренда (few-shot):
{voice_examples}

Задача: на основе новости написать материал-симбиоз «новость × продукт бренда».
Это НЕ пересказ новости. Найди органичные точки пересечения с тем, что бренд
продаёт/делает, добавь собственную экспертизу/угол ({unique_angle}).

Требования SEO/AEO (обязательно): answer-first (40-60 слов в начале каждой секции),
иерархия H1/H2/H3, короткие абзацы/списки, секция FAQ с реальными вопросами,
явные сущности, JSON-LD (Article + FAQPage), строго совпадающий с видимым текстом.
Язык черновика: {language}."""


def build_messages(
    doc: Document, score: RelevanceScore, profile: dict, language: str, products: list[dict]
) -> list[dict]:
    system = SYSTEM_TEMPLATE.format(
        company=profile.get("company_name", ""),
        voice_config=profile.get("voice_config", {}),
        voice_examples=profile.get("voice_examples", []),
        unique_angle=profile.get("unique_angle_hint", "ресейл/архив/винтаж/редкость/стоимость"),
        language=language,
    )
    user = (
        f"Новость: «{doc.title}» ({doc.url}), дата {doc.published_at.isoformat()}.\n"
        f"Почему берём: {score.decision_summary}\n"
        f"Тренд: {score.trend_explanation}\n\n"
        f"Текст новости:\n{doc.body}\n\n"
        f"Товары бренда (опц.): {products}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def generate_draft(
    doc: Document,
    score: RelevanceScore,
    profile: dict,
    tenant_id: str,
    language: str = "en",
    products: list[dict] | None = None,
) -> DraftPost:
    return structured_completion(
        model=settings.llm_model_draft,
        messages=build_messages(doc, score, profile, language, products or []),
        response_model=DraftPost,
        tenant_id=tenant_id,
        stage="draft",
    )
