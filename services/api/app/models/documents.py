"""Каноническая модель документа и извлечённой статьи.

Document — единственная форма, которую видит пайплайн ниже ingestion.
Любой адаптер источника (RSS/скрапер/соцсеть) обязан отдавать Document.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["rss", "scraper", "sitemap", "telegram", "reddit"]


class Document(BaseModel):
    """Нормализованный документ из любого источника."""

    id: str  # hash(source_id + canonical_url)
    tenant_id: str
    source_id: str
    source_type: SourceType
    url: str
    canonical_url: str
    external_id: str | None = None  # GUID / post id
    title: str
    body: str  # markdown
    summary: str | None = None
    language: str | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    media: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    fetched_at: datetime
    content_hash: str
    body_is_complete: bool = False
    metadata: dict = Field(default_factory=dict)


class ExtractedArticle(BaseModel):
    """LLM-обогащение статьи (поля из доков Kate «Что важно сохранять»)."""

    topic: str = Field(description="тема новости одной фразой")
    brands: list[str] = Field(default_factory=list, description="упомянутые бренды")
    items: list[str] = Field(default_factory=list, description="модели/айтемы")
    persons: list[str] = Field(default_factory=list, description="вовлечённые персоны")
    news_type: str = Field(
        description="релиз|коллаборация|назначение|показ|кампания|архив|переиздание|сделка|другое"
    )
    summary: str = Field(description="краткое саммари 2-3 предложения")
    keywords: list[str] = Field(default_factory=list, description="ключевые слова для поиска")
    possible_titles: list[str] = Field(default_factory=list, description="3-5 возможных заголовков")
