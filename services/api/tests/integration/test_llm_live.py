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
from app.models.scoring import RelevanceScore
from app.pipeline.scoring import score_article

pytestmark = pytest.mark.live

PROFILE = {
    "company_name": "LOOTON",
    "company_description": "Ресейл-маркетплейс премиальной и архивной одежды.",
    "audience_description": "Коллекционеры, ресейлеры, ценители архивных и винтажных вещей.",
    "filter_criteria": "Берём релизы, коллаборации, архивы, сделки брендов; отбрасываем офтоп.",
}


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
