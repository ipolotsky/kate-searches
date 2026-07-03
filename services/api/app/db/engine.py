"""Движок и сессии SQLAlchemy.

Коннект идёт под ролью postgres (bypassrls) из DATABASE_URL — это service_role-доступ
для пайплайна и админки, RLS обходится намеренно (см. примечание в 0001_init.sql).
Пользовательские запросы из web скоупятся RLS и идут не отсюда, а через supabase-js.
"""

from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _psycopg_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(_psycopg_url(settings.database_url), pool_pre_ping=True, future=True)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Generator[Session, None, None]:
    with session_scope() as session:
        yield session
