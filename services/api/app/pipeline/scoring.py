"""Стадия скоринга: новость -> RelevanceScore по критериям тенанта.

Использует дешёвую модель (settings.llm_model_score) через LLM-обёртку.
Промпт строится из brand_profile (см. docs/05_ai_pipeline_prompts.md).
"""

from app.config import settings
from app.llm.client import structured_completion
from app.models import Document, RelevanceScore

SYSTEM_TEMPLATE = """Ты — главный редактор и маркетинг-директор бренда {company}.
{company_description}
Твоя аудитория: {audience}.

Критерии отбора этого бренда (что берём, что отбрасываем):
{filter_criteria}

Оцени новость по каждому критерию (low/medium/high) с обоснованием ПЕРЕД баллом,
затем дай итоговый скор 0-100, приоритет HOT/WARM/COLD/DROP и решение.
Бренду интересны инфоповоды, после которых аудитория может захотеть найти, купить,
продать, обсудить или переоценить вещь из новости."""


def build_messages(doc: Document, profile: dict) -> list[dict]:
    system = SYSTEM_TEMPLATE.format(
        company=profile.get("company_name", ""),
        company_description=profile.get("company_description", ""),
        audience=profile.get("audience_description", ""),
        filter_criteria=profile.get("filter_criteria", ""),
    )
    user = (
        f"Заголовок: {doc.title}\n"
        f"Дата: {doc.published_at.isoformat()}\n"
        f"Источник: {doc.url}\n\n"
        f"Текст:\n{doc.body}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def score_article(doc: Document, profile: dict, tenant_id: str) -> RelevanceScore:
    return structured_completion(
        model=settings.llm_model_score,
        messages=build_messages(doc, profile),
        response_model=RelevanceScore,
        tenant_id=tenant_id,
        stage="score",
    )
