"""tenant_month_spend суммирует ai_usage только за окно since (текущий месяц)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.db.engine import session_scope
from app.db.models import AiUsage, Tenant
from app.db.repositories import tenant_month_spend
from app.metering import month_start_utc

pytestmark = pytest.mark.integration


def test_month_spend_sums_only_current_month() -> None:
    name = f"metering-{uuid.uuid4().hex[:8]}"
    since = month_start_utc()
    with session_scope() as session:
        tenant = Tenant(name=name)
        session.add(tenant)
        session.flush()
        tenant_id = tenant.id
        session.add(
            AiUsage(
                tenant_id=tenant_id,
                stage="draft",
                cost_usd=Decimal("0.50"),
                created_at=since + timedelta(days=1),
            )
        )
        session.add(
            AiUsage(
                tenant_id=tenant_id,
                stage="score",
                cost_usd=Decimal("0.25"),
                created_at=datetime.now(UTC),
            )
        )
        # Прошлый месяц — не должен попасть в сумму.
        session.add(
            AiUsage(
                tenant_id=tenant_id,
                stage="draft",
                cost_usd=Decimal("9.00"),
                created_at=since - timedelta(days=2),
            )
        )
    try:
        with session_scope() as session:
            spent = tenant_month_spend(session, tenant_id, since=since)
            assert Decimal(spent) == Decimal("0.75")
    finally:
        with session_scope() as session:
            session.query(AiUsage).filter_by(tenant_id=tenant_id).delete()
            session.query(Tenant).filter_by(id=tenant_id).delete()
