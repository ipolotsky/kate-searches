"""RLS изолирует тенантов: пользователь тенанта A не видит данные тенанта B.

Гоняется против локального Supabase CLI стека (настоящая схема auth + роль authenticated).
Заодно проверяет фикс рекурсии политики на users (security definer у current_tenant_id()).
"""

import json
import uuid
from collections.abc import Iterator

import psycopg
import pytest

from tests.conftest import database_url

pytestmark = pytest.mark.integration


@pytest.fixture
def admin() -> Iterator[psycopg.Connection]:
    """Суперюзер (bypassrls): сидинг, очистка, проверки в обход RLS."""
    with psycopg.connect(database_url(), autocommit=True) as conn:
        yield conn


def _seed_tenant(conn: psycopg.Connection, name: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    article_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute("insert into tenants (id, name) values (%s, %s)", (tenant_id, name))
        cur.execute(
            "insert into users (id, tenant_id, email, role) values (%s, %s, %s, 'owner')",
            (user_id, tenant_id, f"{name}@example.com"),
        )
        cur.execute(
            "insert into articles (id, tenant_id, url, canonical_url, title) "
            "values (%s, %s, %s, %s, %s)",
            (article_id, tenant_id, f"https://{name}.test/a", f"https://{name}.test/a", name),
        )
    return tenant_id, user_id, article_id


def _enter_authenticated(conn: psycopg.Connection, user_id: uuid.UUID) -> psycopg.Cursor:
    """Курсор в транзакции под ролью authenticated с jwt sub = user_id."""
    cur = conn.cursor()
    claims = json.dumps({"sub": str(user_id), "role": "authenticated"})
    cur.execute("select set_config('request.jwt.claims', %s, true)", (claims,))
    cur.execute("set local role authenticated")
    return cur


def test_rls_isolates_tenants(admin: psycopg.Connection) -> None:
    tenant_a, user_a, article_a = _seed_tenant(admin, "tenant-a")
    tenant_b, user_b, article_b = _seed_tenant(admin, "tenant-b")
    try:
        with psycopg.connect(database_url()) as scoped:
            # user A видит только свою статью, чужую — нет.
            cur = _enter_authenticated(scoped, user_a)
            cur.execute("select id from articles")
            visible = {row[0] for row in cur.fetchall()}
            assert article_a in visible
            assert article_b not in visible

            # select из users не рекурсит (проверка фикса security definer)
            # и показывает только пользователей своего тенанта.
            cur.execute("select tenant_id from users")
            assert {row[0] for row in cur.fetchall()} == {tenant_a}
            scoped.rollback()

            # with check блокирует вставку строки с чужим tenant_id.
            cur = _enter_authenticated(scoped, user_a)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    "insert into articles (tenant_id, url, canonical_url, title) "
                    "values (%s, %s, %s, %s)",
                    (tenant_b, "https://x.test/x", "https://x.test/x", "cross-tenant"),
                )
            scoped.rollback()
    finally:
        with admin.cursor() as cur:
            cur.execute("delete from tenants where id = any(%s)", ([tenant_a, tenant_b],))


def test_control_tables_are_read_only(admin: psycopg.Connection) -> None:
    tenant_id, user_id, article_id = _seed_tenant(admin, "tenant-ro")
    try:
        with psycopg.connect(database_url()) as scoped:
            # authenticated НЕ может крутить бюджет своего тенанта.
            cur = _enter_authenticated(scoped, user_id)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    "update tenants set ai_budget_usd_month = 999 where id = %s", (tenant_id,)
                )
            scoped.rollback()

            # НЕ может эскалировать свою роль до owner.
            cur = _enter_authenticated(scoped, user_id)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("update users set role = 'owner' where id = %s", (user_id,))
            scoped.rollback()

            # НЕ может удалить свой тенант (каскадный снос данных).
            cur = _enter_authenticated(scoped, user_id)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("delete from tenants where id = %s", (tenant_id,))
            scoped.rollback()

            # НЕ может подделать строку стоимости.
            cur = _enter_authenticated(scoped, user_id)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    "insert into ai_usage (tenant_id, stage) values (%s, 'score')", (tenant_id,)
                )
            scoped.rollback()

            # Но контент своего тенанта редактировать МОЖЕТ.
            cur = _enter_authenticated(scoped, user_id)
            cur.execute("update articles set title = 'edited' where id = %s", (article_id,))
            assert cur.rowcount == 1
            scoped.rollback()

            # И читать свой тенант — МОЖЕТ.
            cur = _enter_authenticated(scoped, user_id)
            cur.execute("select id from tenants")
            assert {row[0] for row in cur.fetchall()} == {tenant_id}
            scoped.rollback()
    finally:
        with admin.cursor() as cur:
            cur.execute("delete from tenants where id = %s", (tenant_id,))
