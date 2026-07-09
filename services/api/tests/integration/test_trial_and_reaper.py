"""Trial-энфорс (M6.2) и reaper застрявших claim-статусов (M6.1) на реальном Supabase.

Покрывает то, что unit-тесты против реальной БД не трогали: trial-aware reserve (гейтим
и score, и draft через единый ledger-пул period='trial'), expiry-guard, value-fence лимита
драфтов, и reaper reap_stale_claims (scoring->extracted, drafting->scored). Self-cleaning.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.api.routes import _trial_drafts_exhausted
from app.config import settings
from app.db.engine import session_scope
from app.db.models import Article, Post, Tenant
from app.db.repositories import ledger_month_spent
from app.llm.client import _reserve_budget
from app.metering import (
    TRIAL_DEFAULT_DRAFTS_LIMIT,
    TRIAL_PERIOD_KEY,
    BudgetExceededError,
    TrialExpiredError,
    period_key_utc,
)
from app.worker.tasks import reap_stale_claims, score_article

pytestmark = pytest.mark.integration


def _make_tenant(
    session,
    *,
    budget: Decimal,
    status: str | None = None,
    trial_ends_at: datetime | None = None,
    trial_drafts_limit: int | None = None,
) -> uuid.UUID:
    tenant = Tenant(
        name=f"trial-{uuid.uuid4().hex[:8]}",
        ai_budget_usd_month=budget,
        subscription_status=status,
        trial_ends_at=trial_ends_at,
        trial_drafts_limit=trial_drafts_limit,
    )
    session.add(tenant)
    session.flush()
    return tenant.id


def _drop_tenant(tenant_id: uuid.UUID) -> None:
    with session_scope() as session:
        session.query(Tenant).filter_by(id=tenant_id).delete()


def _future() -> datetime:
    return datetime.now(UTC) + timedelta(days=5)


def test_trial_reserve_gates_score_under_trial_period() -> None:
    with session_scope() as session:
        tenant_id = _make_tenant(
            session, budget=Decimal("3"), status="trialing", trial_ends_at=_future()
        )
    try:
        reservation = _reserve_budget(
            tenant_id=str(tenant_id), stage="score", session_factory=session_scope
        )
        assert reservation is not None
        period, estimate = reservation
        assert period == TRIAL_PERIOD_KEY
        with session_scope() as session:
            assert ledger_month_spent(session, tenant_id, period=TRIAL_PERIOD_KEY) == estimate
            # На триальный пул НЕ пишется месячный период — рефилла на стыке месяцев нет.
            assert ledger_month_spent(session, tenant_id, period=period_key_utc()) == Decimal("0")
    finally:
        _drop_tenant(tenant_id)


def test_trial_single_cap_covers_both_score_and_draft() -> None:
    # Единый $3-cap (период 'trial') ограничивает СУММАРНЫЙ COGS: и score, и draft тратят один пул.
    with session_scope() as session:
        tenant_id = _make_tenant(
            session, budget=Decimal("0.1"), status="trialing", trial_ends_at=_future()
        )
    try:
        draft = _reserve_budget(
            tenant_id=str(tenant_id), stage="draft", session_factory=session_scope
        )
        score = _reserve_budget(
            tenant_id=str(tenant_id), stage="score", session_factory=session_scope
        )
        assert draft is not None and draft[0] == TRIAL_PERIOD_KEY
        assert score is not None and score[0] == TRIAL_PERIOD_KEY
        with session_scope() as session:
            # 0.06 (draft) + 0.002 (score) на одном пуле.
            assert ledger_month_spent(session, tenant_id, period=TRIAL_PERIOD_KEY) == Decimal(
                "0.062"
            )
        # Пул почти добит (0.062 < 0.1): ещё draft переступает порог и проходит, следующий — блок.
        crossing = _reserve_budget(
            tenant_id=str(tenant_id), stage="draft", session_factory=session_scope
        )
        assert crossing is not None
        with pytest.raises(BudgetExceededError):
            _reserve_budget(tenant_id=str(tenant_id), stage="draft", session_factory=session_scope)
        # И дешёвый score теперь тоже блокируется тем же исчерпанным триал-пулом.
        with pytest.raises(BudgetExceededError):
            _reserve_budget(tenant_id=str(tenant_id), stage="score", session_factory=session_scope)
    finally:
        _drop_tenant(tenant_id)


def test_non_trial_score_not_gated_but_draft_uses_monthly_period() -> None:
    with session_scope() as session:
        tenant_id = _make_tenant(session, budget=Decimal("10"))  # нет подписки
    try:
        # Дешёвый скоринг вне триала не гейтится вовсе (иначе застревал бы в extracted).
        assert (
            _reserve_budget(tenant_id=str(tenant_id), stage="score", session_factory=session_scope)
            is None
        )
        # Дорогая генерация гейтится, период — календарный месяц (бесплатный сброс).
        reservation = _reserve_budget(
            tenant_id=str(tenant_id), stage="draft", session_factory=session_scope
        )
        assert reservation is not None
        assert reservation[0] == period_key_utc()
        with session_scope() as session:
            assert ledger_month_spent(session, tenant_id, period=TRIAL_PERIOD_KEY) == Decimal("0")
    finally:
        _drop_tenant(tenant_id)


def test_trial_expired_blocks_expensive_call() -> None:
    with session_scope() as session:
        tenant_id = _make_tenant(
            session,
            budget=Decimal("3"),
            status="trialing",
            trial_ends_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    try:
        # Окно между trial_end и вебхуком-даунгрейдом: дорогие вызовы не жжём.
        with pytest.raises(TrialExpiredError):
            _reserve_budget(tenant_id=str(tenant_id), stage="draft", session_factory=session_scope)
        # TrialExpiredError — подкласс BudgetExceededError (обработчики трактуют как budget-block).
        assert issubclass(TrialExpiredError, BudgetExceededError)
    finally:
        _drop_tenant(tenant_id)


def test_trial_drafts_value_fence() -> None:
    with session_scope() as session:
        tenant_id = _make_tenant(
            session,
            budget=Decimal("3"),
            status="trialing",
            trial_ends_at=_future(),
            trial_drafts_limit=2,
        )
        for _ in range(2):
            session.add(
                Post(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    faq=[],
                    seo={},
                    suggested_titles=[],
                    status="new",
                )
            )
    try:
        with session_scope() as session:
            tenant = session.get(Tenant, tenant_id)
            assert _trial_drafts_exhausted(session, tenant) is True
        # Один пост < лимита 2 -> ещё не исчерпан.
        with session_scope() as session:
            one = session.query(Post).filter_by(tenant_id=tenant_id).first()
            session.delete(one)
        with session_scope() as session:
            tenant = session.get(Tenant, tenant_id)
            assert _trial_drafts_exhausted(session, tenant) is False
        # Вне триала лимит драфтов не действует, даже при куче постов.
        with session_scope() as session:
            tenant = session.get(Tenant, tenant_id)
            tenant.subscription_status = None
        with session_scope() as session:
            tenant = session.get(Tenant, tenant_id)
            assert _trial_drafts_exhausted(session, tenant) is False
    finally:
        _drop_tenant(tenant_id)


def test_trial_drafts_default_limit_applies_without_override() -> None:
    with session_scope() as session:
        tenant_id = _make_tenant(
            session, budget=Decimal("3"), status="trialing", trial_ends_at=_future()
        )
        for _ in range(TRIAL_DEFAULT_DRAFTS_LIMIT):
            session.add(
                Post(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    faq=[],
                    seo={},
                    suggested_titles=[],
                    status="new",
                )
            )
    try:
        with session_scope() as session:
            tenant = session.get(Tenant, tenant_id)
            assert tenant.trial_drafts_limit is None
            assert _trial_drafts_exhausted(session, tenant) is True
    finally:
        _drop_tenant(tenant_id)


def _article(tenant_id: uuid.UUID, slug: str, status: str, changed_at: datetime) -> Article:
    return Article(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        url=f"https://reap.test/{slug}",
        canonical_url=f"https://reap.test/{slug}",
        title=slug,
        status=status,
        status_changed_at=changed_at,
    )


def test_reaper_frees_stale_claims_and_requeues_scoring(monkeypatch: pytest.MonkeyPatch) -> None:
    stale = datetime.now(UTC) - timedelta(minutes=settings.claim_stale_minutes + 5)
    fresh = datetime.now(UTC)
    with session_scope() as session:
        tenant_id = _make_tenant(session, budget=Decimal("10"))
        stale_scoring = _article(tenant_id, "stale-scoring", "scoring", stale)
        stale_drafting = _article(tenant_id, "stale-drafting", "drafting", stale)
        fresh_scoring = _article(tenant_id, "fresh-scoring", "scoring", fresh)
        session.add_all([stale_scoring, stale_drafting, fresh_scoring])
        session.flush()
        stale_scoring_id = stale_scoring.id
        stale_drafting_id = stale_drafting.id
        fresh_scoring_id = fresh_scoring.id

    requeued: list[str] = []
    monkeypatch.setattr(score_article, "delay", lambda *args, **kwargs: requeued.append(args))
    try:
        result = reap_stale_claims()

        assert result["rescored"] == 1
        assert result["drafting_released"] == 1
        # Застрявший scoring пере-поставлен в очередь для повторного скоринга.
        assert len(requeued) == 1
        assert requeued[0][0] == str(stale_scoring_id)

        with session_scope() as session:
            assert session.get(Article, stale_scoring_id).status == "extracted"
            assert session.get(Article, stale_drafting_id).status == "scored"
            # Свежий claim (в пределах порога) не трогается.
            assert session.get(Article, fresh_scoring_id).status == "scoring"
    finally:
        _drop_tenant(tenant_id)
