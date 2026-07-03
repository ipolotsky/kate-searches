"""БД-слой пишет и читает через сессию service_role (обход RLS)."""

import uuid

import pytest

from app.db.engine import session_scope
from app.db.models import AiUsage, Tenant

pytestmark = pytest.mark.integration


def test_insert_and_read_tenant() -> None:
    name = f"db-layer-{uuid.uuid4().hex[:8]}"
    with session_scope() as session:
        tenant = Tenant(name=name)
        session.add(tenant)
        session.flush()
        tenant_id = tenant.id
    try:
        with session_scope() as session:
            got = session.get(Tenant, tenant_id)
            assert got is not None
            assert got.name == name
            assert got.plan == "pilot"
    finally:
        with session_scope() as session:
            session.query(AiUsage).filter_by(tenant_id=tenant_id).delete()
            session.query(Tenant).filter_by(id=tenant_id).delete()
