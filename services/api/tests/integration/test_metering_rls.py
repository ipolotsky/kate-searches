"""RLS/грант-контракт метеринг-RPC (M5), изолированно на реальном Supabase-стеке.

owner-RPC (security invoker) скоупят расход к своему тенанту; admin-RPC (security definer)
не вызываемы под authenticated. Сидинг/очистка — через суперюзера (bypassrls), self-cleaning.
"""

import json
import uuid
from collections.abc import Iterator
from decimal import Decimal

import psycopg
import pytest

from tests.conftest import database_url

pytestmark = pytest.mark.integration


@pytest.fixture
def admin() -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url(), autocommit=True) as conn:
        yield conn


def _seed(
    conn: psycopg.Connection, name: str, spend: list[tuple[str, str]]
) -> tuple[uuid.UUID, uuid.UUID]:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute("insert into tenants (id, name) values (%s, %s)", (tenant_id, name))
        cur.execute(
            "insert into users (id, tenant_id, email, role) values (%s, %s, %s, 'owner')",
            (user_id, tenant_id, f"{name}@example.com"),
        )
        for stage, cost in spend:
            cur.execute(
                "insert into ai_usage (tenant_id, stage, cost_usd) values (%s, %s, %s)",
                (tenant_id, stage, cost),
            )
    return tenant_id, user_id


def _enter_authenticated(conn: psycopg.Connection, user_id: uuid.UUID) -> psycopg.Cursor:
    cur = conn.cursor()
    claims = json.dumps({"sub": str(user_id), "role": "authenticated"})
    cur.execute("select set_config('request.jwt.claims', %s, true)", (claims,))
    cur.execute("set local role authenticated")
    return cur


def test_owner_rpc_scopes_spend_to_own_tenant(admin: psycopg.Connection) -> None:
    tenant_a, user_a = _seed(admin, "meter-a", [("draft", "0.50"), ("score", "0.10")])
    tenant_b, user_b = _seed(admin, "meter-b", [("draft", "9.99")])
    try:
        with psycopg.connect(database_url()) as scoped:
            cur = _enter_authenticated(scoped, user_a)
            cur.execute("select tenant_month_spend()")
            assert cur.fetchone()[0] == Decimal("0.60")

            cur.execute(
                "select stage, cost_usd, calls from tenant_month_usage_by_stage() order by stage"
            )
            rows = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
            assert rows == {"draft": (Decimal("0.50"), 1), "score": (Decimal("0.10"), 1)}
            scoped.rollback()

            # user B видит только свой расход, не сумму обоих тенантов.
            cur = _enter_authenticated(scoped, user_b)
            cur.execute("select tenant_month_spend()")
            assert cur.fetchone()[0] == Decimal("9.99")
            scoped.rollback()
    finally:
        with admin.cursor() as cur:
            cur.execute("delete from tenants where id = any(%s)", ([tenant_a, tenant_b],))


def test_admin_rpc_denied_for_authenticated(admin: psycopg.Connection) -> None:
    tenant_id, user_id = _seed(admin, "meter-admin", [("draft", "1.00")])
    try:
        with psycopg.connect(database_url()) as scoped:
            cur = _enter_authenticated(scoped, user_id)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("select * from admin_tenant_report(date_trunc('month', now()))")
            scoped.rollback()

            cur = _enter_authenticated(scoped, user_id)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    "select * from admin_tenant_usage_by_stage(%s, date_trunc('month', now()))",
                    (tenant_id,),
                )
            scoped.rollback()
    finally:
        with admin.cursor() as cur:
            cur.execute("delete from tenants where id = %s", (tenant_id,))


def test_platform_admins_self_select_and_not_writable(admin: psycopg.Connection) -> None:
    tenant_id, user_id = _seed(admin, "meter-padmin", [])
    other_tenant, other_user = _seed(admin, "meter-pother", [])
    with admin.cursor() as cur:
        cur.execute("insert into platform_admins (user_id) values (%s)", (other_user,))
    try:
        with psycopg.connect(database_url()) as scoped:
            # Не-админ не видит чужую строку platform_admins (и свою тоже, т.к. её нет).
            cur = _enter_authenticated(scoped, user_id)
            cur.execute("select count(*) from platform_admins")
            assert cur.fetchone()[0] == 0
            scoped.rollback()

            # Участник не может вписать себя в platform_admins (эскалация).
            cur = _enter_authenticated(scoped, user_id)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("insert into platform_admins (user_id) values (%s)", (user_id,))
            scoped.rollback()

            # Админ видит ровно свою строку (self-select).
            cur = _enter_authenticated(scoped, other_user)
            cur.execute("select user_id from platform_admins")
            assert {row[0] for row in cur.fetchall()} == {other_user}
            scoped.rollback()
    finally:
        with admin.cursor() as cur:
            cur.execute("delete from tenants where id = any(%s)", ([tenant_id, other_tenant],))
