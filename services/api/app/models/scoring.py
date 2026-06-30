"""Схема скоринга релевантности — прямой перевод «Критериев отбора» LOOTON.

Веса критериев и порог берутся из brand_profiles тенанта (тенант-настраиваемо).
"""

from typing import Literal

from pydantic import BaseModel, Field

Level = Literal["low", "medium", "high"]


class CriterionScore(BaseModel):
    # reasoning ПЕРЕД score — дешёвый chain-of-thought, повышает надёжность
    reasoning: str = Field(description="почему такой балл — пиши до score")
    score: Level


class RelevanceScore(BaseModel):
    """Оценка новости по критериям бренда + агрегат и приоритет публикации."""

    news_potential: CriterionScore
    resale_potential: CriterionScore
    commercial_potential: CriterionScore
    trend_potential: CriterionScore
    trend_explanation: str = Field(description="какой именно тренд подтверждает/запускает")
    seo_potential: CriterionScore
    aeo_potential: CriterionScore
    content_potential: CriterionScore
    content_cluster_potential: CriterionScore
    knowledge_gap_potential: CriterionScore
    unique_angle: CriterionScore

    overall_score: int = Field(ge=0, le=100, description="взвешенная итоговая релевантность")
    publication_priority: Literal["HOT", "WARM", "COLD", "DROP"]
    passes_threshold: bool
    decision_summary: str = Field(description="1-2 предложения: почему берём/не берём")
