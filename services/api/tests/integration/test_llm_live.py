"""Реальный скоринг через LiteLLM: тестовая статья -> валидный RelevanceScore + ai_usage.

Гейт: RUN_LIVE_LLM=1 + ключ провайдера (LLM_MODEL_SCORE). Пишет строку в ai_usage,
при langfuse_enabled=true уходит трейс в локальный Langfuse.
"""

import uuid
from datetime import UTC, datetime

import pytest

from app.db.engine import session_scope
from app.db.models import AiUsage, Tenant
from app.models.documents import Document
from app.models.drafts import DraftPost
from app.models.scoring import CriterionScore, RelevanceScore
from app.pipeline.generation import generate_draft
from app.pipeline.scoring import score_article

pytestmark = pytest.mark.live

PROFILE = {
    "company_name": "LOOTON",
    "company_description": "Ресейл-маркетплейс премиальной и архивной одежды.",
    "audience_description": "Коллекционеры, ресейлеры, ценители архивных и винтажных вещей.",
    "filter_criteria": "Берём релизы, коллаборации, архивы, сделки брендов; отбрасываем офтоп.",
}

GEN_PROFILE = {
    "company_name": "LOOTON",
    "voice_config": {"tone": "экспертный, уверенный, без воды"},
    "voice_examples": [],
    "unique_angle_hint": "ресейл/архив/винтаж/редкость/стоимость",
}


def _relevance() -> RelevanceScore:
    criterion = CriterionScore(reasoning="сильный ресейл-сигнал", score="high")
    return RelevanceScore(
        news_potential=criterion,
        resale_potential=criterion,
        commercial_potential=criterion,
        trend_potential=criterion,
        trend_explanation="рост спроса на архивные релизы",
        seo_potential=criterion,
        aeo_potential=criterion,
        content_potential=criterion,
        content_cluster_potential=criterion,
        knowledge_gap_potential=criterion,
        unique_angle=criterion,
        overall_score=85,
        publication_priority="HOT",
        passes_threshold=True,
        decision_summary="берём: сильный ресейл-инфоповод",
    )


def _document(tenant_id: uuid.UUID) -> Document:
    now = datetime.now(UTC)
    return Document(
        id=uuid.uuid4().hex,
        tenant_id=str(tenant_id),
        source_id=str(uuid.uuid4()),
        source_type="rss",
        url="https://example.test/nike-archive-drop",
        canonical_url="https://example.test/nike-archive-drop",
        title="Nike переиздаёт архивную коллекцию 2003 года",
        body="Nike анонсировала переиздание культовой архивной линейки кроссовок 2003 года. "
        "Лимитированный дроп, ожидается высокий ресейл-спрос.",
        published_at=now,
        fetched_at=now,
        content_hash="hash",
    )


def test_live_scoring_returns_valid_relevance() -> None:
    with session_scope() as session:
        tenant = Tenant(name=f"live-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        session.flush()
        tenant_id = tenant.id
    try:
        score = score_article(_document(tenant_id), PROFILE, str(tenant_id))
        assert isinstance(score, RelevanceScore)
        assert 0 <= score.overall_score <= 100
        with session_scope() as session:
            rows = session.query(AiUsage).filter_by(tenant_id=tenant_id).all()
            assert len(rows) == 1
            assert rows[0].stage == "score"
            assert rows[0].request_id
    finally:
        with session_scope() as session:
            session.query(AiUsage).filter_by(tenant_id=tenant_id).delete()
            session.query(Tenant).filter_by(id=tenant_id).delete()


def test_live_generation_returns_valid_draft() -> None:
    with session_scope() as session:
        tenant = Tenant(name=f"live-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        session.flush()
        tenant_id = tenant.id
    try:
        draft, cost = generate_draft(
            _document(tenant_id), _relevance(), GEN_PROFILE, str(tenant_id), "ru"
        )
        assert isinstance(draft, DraftPost)
        assert draft.body_markdown.strip()
        assert len(draft.suggested_titles) >= 3
        assert cost >= 0
        with session_scope() as session:
            rows = session.query(AiUsage).filter_by(tenant_id=tenant_id).all()
            assert len(rows) == 1
            assert rows[0].stage == "draft"
            assert rows[0].request_id
    finally:
        with session_scope() as session:
            session.query(AiUsage).filter_by(tenant_id=tenant_id).delete()
            session.query(Tenant).filter_by(id=tenant_id).delete()
