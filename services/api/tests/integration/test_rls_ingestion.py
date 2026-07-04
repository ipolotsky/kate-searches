"""RLS для control-таблиц M1: pipeline_runs/article_sources read-only, source_secrets скрыта.

Проверяет DoD §14 п.6: authenticated не пишет леджер/провенанс и не видит секреты.
Заодно закрывает регресс TRUNCATE-дыры (TRUNCATE обходит RLS).
"""

import uuid
from collections.abc import Iterator

import psycopg
import pytest

from tests.conftest import database_url

pytestmark = pytest.mark.integration


@pytest.fixture
def admin() -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url(), autocommit=True) as conn:
        yield conn


def _seed(conn: psycopg.Connection) -> tuple[uuid.UUID, uuid.UUID]:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute("insert into tenants (id, name) values (%s, 'rls-m1')", (tenant_id,))
        cur.execute(
            "insert into users (id, tenant_id, email, role) values (%s, %s, %s, 'owner')",
            (user_id, tenant_id, "rls-m1@example.com"),
        )
        cur.execute(
            "insert into pipeline_runs (tenant_id, run_date) values (%s, current_date)",
            (tenant_id,),
        )
    return tenant_id, user_id


def _enter_authenticated(conn: psycopg.Connection, user_id: uuid.UUID) -> psycopg.Cursor:
    import json

    cur = conn.cursor()
    claims = json.dumps({"sub": str(user_id), "role": "authenticated"})
    cur.execute("select set_config('request.jwt.claims', %s, true)", (claims,))
    cur.execute("set local role authenticated")
    return cur


def test_pipeline_runs_read_only(admin: psycopg.Connection) -> None:
    tenant_id, user_id = _seed(admin)
    try:
        with psycopg.connect(database_url()) as scoped:
            cur = _enter_authenticated(scoped, user_id)
            cur.execute("select tenant_id from pipeline_runs")
            assert {row[0] for row in cur.fetchall()} == {tenant_id}
            scoped.rollback()

            cur = _enter_authenticated(scoped, user_id)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    "insert into pipeline_runs (tenant_id, run_date) values (%s, current_date)",
                    (tenant_id,),
                )
            scoped.rollback()

            cur = _enter_authenticated(scoped, user_id)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    "update pipeline_runs set status = 'failed' where tenant_id = %s", (tenant_id,)
                )
            scoped.rollback()

            cur = _enter_authenticated(scoped, user_id)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("truncate pipeline_runs")
            scoped.rollback()
    finally:
        with admin.cursor() as cur:
            cur.execute("delete from tenants where id = %s", (tenant_id,))


def test_source_secrets_hidden(admin: psycopg.Connection) -> None:
    tenant_id, user_id = _seed(admin)
    try:
        with psycopg.connect(database_url()) as scoped:
            cur = _enter_authenticated(scoped, user_id)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("select * from source_secrets")
            scoped.rollback()

            cur = _enter_authenticated(scoped, user_id)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("truncate source_secrets")
            scoped.rollback()
    finally:
        with admin.cursor() as cur:
            cur.execute("delete from tenants where id = %s", (tenant_id,))


def test_m0_control_tables_no_truncate(admin: psycopg.Connection) -> None:
    tenant_id, user_id = _seed(admin)
    try:
        with psycopg.connect(database_url()) as scoped:
            for table in ("tenants", "users", "ai_usage"):
                cur = _enter_authenticated(scoped, user_id)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    cur.execute(f"truncate {table}")
                scoped.rollback()
    finally:
        with admin.cursor() as cur:
            cur.execute("delete from tenants where id = %s", (tenant_id,))
