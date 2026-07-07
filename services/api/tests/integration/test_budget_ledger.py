"""Атомарный леджер бюджета (reserve/settle) на реальном Supabase, self-cleaning."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.db.engine import session_scope
from app.db.models import Article, BrandProfile, Tenant
from app.db.repositories import ledger_month_spent, reserve_budget, settle_budget
from app.metering import BudgetExceededError
from app.models.scoring import CriterionScore, RelevanceScore
from app.pipeline.generation import generate_draft_run
from app.pipeline.scoring import score_article_run

pytestmark = pytest.mark.integration


def _relevance_dict() -> dict:
    criterion = CriterionScore(reasoning="ok", score="high")
    return RelevanceScore(
        news_potential=criterion,
        resale_potential=criterion,
        commercial_potential=criterion,
        trend_potential=criterion,
        trend_explanation="t",
        seo_potential=criterion,
        aeo_potential=criterion,
        content_potential=criterion,
        content_cluster_potential=criterion,
        knowledge_gap_potential=criterion,
        unique_angle=criterion,
        overall_score=80,
        publication_priority="HOT",
        passes_threshold=True,
        decision_summary="take",
    ).model_dump()


def _tenant(session, budget: Decimal) -> uuid.UUID:
    tenant = Tenant(name=f"ledger-{uuid.uuid4().hex[:8]}", ai_budget_usd_month=budget)
    session.add(tenant)
    session.flush()
    return tenant.id


def test_reserve_allows_until_budget_reached_then_blocks() -> None:
    with session_scope() as session:
        tenant_id = _tenant(session, Decimal("1"))
    try:
        with session_scope() as session:

            def reserve() -> bool:
                return reserve_budget(
                    session,
                    tenant_id,
                    period="2026-07",
                    estimate=Decimal("0.4"),
                    budget=Decimal("1"),
                )

            assert reserve() is True  # 0 -> 0.4  (spent<1)
            assert reserve() is True  # 0.4 -> 0.8
            assert reserve() is True  # 0.8 -> 1.2 (вызов, пересекающий бюджет, проходит)
            assert reserve() is False  # 1.2 >= 1 -> блок
            assert ledger_month_spent(session, tenant_id, period="2026-07") == Decimal("1.2")
    finally:
        with session_scope() as session:
            session.query(Tenant).filter_by(id=tenant_id).delete()


def test_settle_reconciles_reservation_to_actual_cost() -> None:
    with session_scope() as session:
        tenant_id = _tenant(session, Decimal("10"))
    try:
        with session_scope() as session:
            reserve_budget(
                session, tenant_id, period="2026-07", estimate=Decimal("0.06"), budget=Decimal("10")
            )
            settle_budget(
                session, tenant_id, period="2026-07", delta=Decimal("0.005") - Decimal("0.06")
            )
            assert ledger_month_spent(session, tenant_id, period="2026-07") == Decimal("0.005")
    finally:
        with session_scope() as session:
            session.query(Tenant).filter_by(id=tenant_id).delete()


def test_refund_returns_reservation_on_failure() -> None:
    with session_scope() as session:
        tenant_id = _tenant(session, Decimal("10"))
    try:
        with session_scope() as session:
            reserve_budget(
                session, tenant_id, period="2026-07", estimate=Decimal("0.06"), budget=Decimal("10")
            )
            settle_budget(session, tenant_id, period="2026-07", delta=-Decimal("0.06"))
            assert ledger_month_spent(session, tenant_id, period="2026-07") == Decimal("0")
    finally:
        with session_scope() as session:
            session.query(Tenant).filter_by(id=tenant_id).delete()


def test_scoring_stage_blocked_when_budget_zero_leaves_article_extracted() -> None:
    # budget=0 => _reserve_budget рейзит BudgetExceededError ДО обращения к модели.
    with session_scope() as session:
        tenant = Tenant(name=f"cap-{uuid.uuid4().hex[:8]}", ai_budget_usd_month=Decimal("0"))
        session.add(tenant)
        session.flush()
        tenant_id = tenant.id
        session.add(BrandProfile(tenant_id=tenant_id, filter_criteria="x", score_threshold=60))
        article = Article(
            tenant_id=tenant_id,
            url="https://n.example/a",
            canonical_url="https://n.example/a",
            title="Fresh drop",
            body="word " * 80,
            language="en",
            published_at=datetime.now(UTC),
            status="extracted",
        )
        session.add(article)
        session.flush()
        article_id = article.id
    try:
        with session_scope() as session:
            with pytest.raises(BudgetExceededError):
                score_article_run(session, article_id, uuid.uuid4())
        with session_scope() as session:
            assert session.get(Article, article_id).status == "extracted"
    finally:
        with session_scope() as session:
            session.query(Tenant).filter_by(id=tenant_id).delete()


def test_generation_stage_blocked_when_budget_zero_releases_claim() -> None:
    with session_scope() as session:
        tenant = Tenant(name=f"cap-{uuid.uuid4().hex[:8]}", ai_budget_usd_month=Decimal("0"))
        session.add(tenant)
        session.flush()
        tenant_id = tenant.id
        session.add(BrandProfile(tenant_id=tenant_id, filter_criteria="x", locales=["en"]))
        article = Article(
            tenant_id=tenant_id,
            url="https://n.example/g",
            canonical_url="https://n.example/g",
            title="Fresh drop",
            body="word " * 80,
            language="en",
            published_at=datetime.now(UTC),
            status="scored",
            relevance=_relevance_dict(),
            relevance_score=80,
        )
        session.add(article)
        session.flush()
        article_id = article.id
    try:
        with pytest.raises(BudgetExceededError):
            generate_draft_run(article_id)
        # claim откатан: статья вернулась в scored (не застряла в drafting), поста нет.
        with session_scope() as session:
            assert session.get(Article, article_id).status == "scored"
    finally:
        with session_scope() as session:
            session.query(Tenant).filter_by(id=tenant_id).delete()


def test_periods_are_independent_monthly_reset() -> None:
    with session_scope() as session:
        tenant_id = _tenant(session, Decimal("1"))
    try:
        with session_scope() as session:
            reserve_budget(
                session, tenant_id, period="2026-07", estimate=Decimal("0.9"), budget=Decimal("1")
            )
            # Новый период стартует с нуля — бесплатный месячный сброс.
            allowed = reserve_budget(
                session, tenant_id, period="2026-08", estimate=Decimal("0.9"), budget=Decimal("1")
            )
            assert allowed is True
            assert ledger_month_spent(session, tenant_id, period="2026-07") == Decimal("0.9")
            assert ledger_month_spent(session, tenant_id, period="2026-08") == Decimal("0.9")
    finally:
        with session_scope() as session:
            session.query(Tenant).filter_by(id=tenant_id).delete()
