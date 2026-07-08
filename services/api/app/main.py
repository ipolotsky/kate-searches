"""Точка входа FastAPI-сервиса."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.api import router
from app.config import settings
from app.db.engine import engine

app = FastAPI(title="KateSearches API", version=__version__)
app.include_router(router)


@app.get("/health")
def health() -> dict:
    """Liveness: процесс поднят. Дёшево, без внешних зависимостей."""
    return {"status": "ok", "version": __version__}


@app.get("/ready")
def ready() -> JSONResponse:
    """Readiness: реальная проба БД (SELECT 1) и брокера (Redis PING).

    На эту ручку завязан healthcheck-gated docker rollout. Статичный /health не отлавливал
    контейнер с мёртвой/неверной БД (движок ленивый, коннекта на импорте нет) и rollout мог
    переключить трафик на нерабочую реплику. 503 при недоступности зависимости — чтобы rollout
    провалил healthcheck и не переключался.
    """
    checks: dict[str, str] = {}
    ok = True

    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "down"
        ok = False

    try:
        import redis

        redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "down"
        ok = False

    payload = {"status": "ok" if ok else "unavailable", "version": __version__, "checks": checks}
    return JSONResponse(payload, status_code=200 if ok else 503)
