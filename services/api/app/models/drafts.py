"""Схема черновика поста — тело + AEO-разметка одним структурированным ответом.

Тело и JSON-LD генерируются вместе, чтобы схема всегда совпадала с контентом.
"""

from pydantic import BaseModel, Field


class FAQItem(BaseModel):
    question: str
    answer: str = Field(description="прямой ответ 40-60 слов")


class DraftPost(BaseModel):
    language: str = Field(description="язык черновика, напр. 'ru' или 'en'")
    title: str
    suggested_titles: list[str] = Field(min_length=3)
    meta_description: str = Field(max_length=200)
    body_markdown: str = Field(description="answer-first, H2/H3, короткие абзацы, списки")
    faq: list[FAQItem] = Field(description="реальные Q&A как спрашивают пользователи")
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list, description="люди/бренды/модели/места")
    brand_tie_in: str = Field(
        description="как инфоповод органично связан с брендом — угол симбиоза «инфоповод × бренд»"
    )
    seo_instructions: str = Field(description="что прописать в разметке/семантике")
    json_ld: dict = Field(description="schema.org Article + FAQPage + BreadcrumbList")
