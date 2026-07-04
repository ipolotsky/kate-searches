"""REST-эндпоинты сервиса.

/internal/pipeline/run — claim дневного прогона + постановка в Celery.
/internal/sources/test — синхронный dry-run адаптера без записи в БД (UI при добавлении источника).
"""

import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ValidationError

from app.adapters import REGISTRY
from app.adapters.base import FetchRequest
from app.db.engine import session_scope
from app.db.models import Tenant
from app.db.repositories import PipelineRunRepository
from app.pipeline.dedup import _safe_zone, is_novel

router = APIRouter()

_TEST_TIMEOUT_SECONDS = 15.0


class RunPipelineRequest(BaseModel):
    tenant_id: str
    mode: str = "incremental"


class RunPipelineResponse(BaseModel):
    tenant_id: str
    queued: bool
    run_id: str | None = None
    detail: str


@router.post("/internal/pipeline/run", response_model=RunPipelineResponse)
def run_pipeline(req: RunPipelineRequest) -> RunPipelineResponse:
    """Запустить дневной прогон для тенанта: claim run + enqueue Celery."""
    tenant_uuid = uuid.UUID(req.tenant_id)
    with session_scope() as session:
        tenant = session.get(Tenant, tenant_uuid)
        timezone = tenant.timezone if tenant is not None else "UTC"
        run_date = datetime.now(UTC).astimezone(_safe_zone(timezone)).date()
        run_id = PipelineRunRepository.claim_run(
            session, tenant_id=tenant_uuid, run_date=run_date, mode=req.mode
        )

    if run_id is None:
        return RunPipelineResponse(
            tenant_id=req.tenant_id, queued=False, detail="run already claimed for today"
        )

    try:
        from app.worker.tasks import run_tenant_pipeline

        run_tenant_pipeline.delay(str(tenant_uuid), str(run_id), req.mode, None)
        queued = True
        detail = "queued"
    except Exception as exc:
        queued = False
        detail = f"claimed but not queued: {exc}"

    return RunPipelineResponse(
        tenant_id=req.tenant_id, queued=queued, run_id=str(run_id), detail=detail
    )


class TestSourceRequest(BaseModel):
    type: str
    url: str
    config: dict = {}
    tenant_id: str | None = None


@router.post("/internal/sources/test")
async def test_source(req: TestSourceRequest) -> dict:
    """Синхронный dry-run адаптера: sample + is_novel + warnings без записи в БД."""
    if req.type not in REGISTRY:
        return {
            "ok": False,
            "supported": False,
            "error": "unsupported_type",
            "supported_types": REGISTRY.types(),
        }

    adapter = REGISTRY[req.type]
    try:
        adapter.validate_config(req.config)
    except ValidationError as exc:
        return {"ok": False, "error": "invalid_config", "fields": exc.errors(include_url=False)}

    source = {"id": None, "tenant_id": req.tenant_id, "url": req.url, "config": req.config}
    request = FetchRequest(source=source, state={}, mode="test", limit=5)

    try:
        result = await asyncio.wait_for(
            run_in_threadpool(adapter.fetch, request), timeout=_TEST_TIMEOUT_SECONDS
        )
    except TimeoutError:
        return {"ok": False, "error": "fetch_timeout"}
    except Exception as exc:
        return {"ok": False, "error": "fetch_error", "detail": str(exc)}

    timezone = _tenant_timezone(req.tenant_id)
    sample = []
    for raw in result.items[:5]:
        try:
            doc = adapter.normalize(source, raw)
        except Exception:
            continue
        sample.append(
            {
                "title": doc.title,
                "url": doc.url,
                "canonical_url": doc.canonical_url,
                "published_at": doc.published_at.isoformat() if doc.published_at else None,
                "is_novel": is_novel(doc.published_at, timezone),
                "language": doc.language,
                "has_body": bool(doc.body),
                "body_preview": (doc.body or "")[:200],
            }
        )

    error = None
    if not result.items and "empty_feed" in result.warnings:
        error = "empty_feed"
    return {
        "ok": True,
        "supported": True,
        "capabilities": adapter.capabilities.model_dump(),
        "cursor_kind": adapter.capabilities.cursor_kind,
        "stats": result.stats.model_dump(),
        "warnings": result.warnings,
        "sample": sample,
        "error": error,
    }


def _tenant_timezone(tenant_id: str | None) -> str:
    if not tenant_id:
        return "UTC"
    try:
        with session_scope() as session:
            tenant = session.get(Tenant, uuid.UUID(tenant_id))
            return tenant.timezone if tenant is not None else "UTC"
    except Exception:
        return "UTC"
