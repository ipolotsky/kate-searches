"""Атомарный леджер бюджета (reserve/settle) на реальном Supabase, self-cleaning."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import instructor
import litellm
import pytest

from app.db.engine import session_scope
from app.db.models import Article, BrandProfile, Tenant
from app.db.repositories import ledger_month_spent, reserve_budget, settle_budget
from app.llm import client as llm_client
from app.metering import BudgetExceededError, period_key_utc
from app.models.scoring import CriterionScore, RelevanceScore
from app.pipeline.generation import generate_draft_run
from app.pipeline.scoring import score_article_run

pytestmark = pytest.mark.integration


def _relevance() -> RelevanceScore:
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
    )


def _relevance_dict() -> dict:
    return _relevance().model_dump()


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


def test_scoring_stage_not_gated_by_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    # Скоринг НЕ гейтится бюджетом (hard-cap только на генерации). budget=0 не блокирует score:
    # статья доходит до scored/filtered_out, а не застревает в extracted. LLM замокан.
    from app.pipeline import scoring as scoring_mod

    monkeypatch.setattr(scoring_mod, "score_article", lambda *a, **k: _relevance())

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
        result = score_article_run(article_id, uuid.uuid4())
        assert result["status"] == "scored"
        with session_scope() as session:
            assert session.get(Article, article_id).status == "scored"
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


class _RaisingInstructor:
    """Инструктор, который фаертся хуком на каждый ответ, затем бросает (ретраи исчерпаны)."""

    def __init__(self, responses: list) -> None:
        self._responses = responses
        self._hooks: dict = {}
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create_with_completion=self._create)
        )

    def on(self, event: str, handler) -> None:
        self._hooks.setdefault(event, []).append(handler)

    def _create(self, **_: object):
        for response in self._responses:
            for handler in self._hooks.get("completion:response", []):
                handler(response)
        raise RuntimeError("validation exhausted")


def test_failed_call_with_paid_retries_settles_ledger_not_full_refund(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Провал вызова после оплаченных ретраев сводит ledger к реальному расходу, а не рефандит в 0
    # (иначе hard-cap не увидел бы сожжённые деньги). draft гейтится, бюджет 10 -> резерв 0.06.
    with session_scope() as session:
        tenant_id = _tenant(session, Decimal("10"))
    try:
        responses = [
            SimpleNamespace(usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10)),
            SimpleNamespace(usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10)),
        ]
        monkeypatch.setattr(instructor, "from_litellm", lambda _fn: _RaisingInstructor(responses))
        monkeypatch.setattr(litellm, "completion_cost", lambda **_: 0.02)

        with pytest.raises(RuntimeError):
            llm_client.structured_completion_with_usage(
                model="openai/gpt-5-mini",
                messages=[{"role": "user", "content": "x"}],
                response_model=RelevanceScore,
                tenant_id=str(tenant_id),
                stage="draft",
            )

        with session_scope() as session:
            # резерв 0.06 сведён к факту 0.04 (2 попытки * 0.02), а не рефанднут в 0.
            spent = ledger_month_spent(session, tenant_id, period=period_key_utc())
            assert spent == Decimal("0.04")
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
