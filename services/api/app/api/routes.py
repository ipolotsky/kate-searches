"""REST-эндпоинты сервиса.

Внутренние (пайплайн) дёргаются Celery beat / админкой.
Публичные читаются через BFF Next.js.
Сейчас — контракт + заглушки; БД-слой подключаем в M0/M1.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class RunPipelineRequest(BaseModel):
    tenant_id: str


class RunPipelineResponse(BaseModel):
    tenant_id: str
    queued: bool
    detail: str


@router.post("/internal/pipeline/run", response_model=RunPipelineResponse)
def run_pipeline(req: RunPipelineRequest) -> RunPipelineResponse:
    """Запустить дневной прогон для тенанта.

    TODO(M1): поставить задачу в Celery: ingest -> extract -> dedup -> score -> generate.
    """
    return RunPipelineResponse(
        tenant_id=req.tenant_id,
        queued=False,
        detail="pipeline not wired yet (M1)",
    )


class TestSourceRequest(BaseModel):
    type: str
    url: str


@router.post("/internal/sources/test")
def test_source(req: TestSourceRequest) -> dict:
    """Проверить, что источник парсится (используется в UI при добавлении).

    TODO(M1): прогнать адаптер из REGISTRY[req.type] и вернуть пример элементов.
    """
    from app.adapters import REGISTRY

    supported = req.type in REGISTRY
    return {"type": req.type, "supported": supported, "url": req.url}
