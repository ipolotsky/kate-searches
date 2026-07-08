"""REST-эндпоинты сервиса.

/internal/pipeline/run — claim дневного прогона + постановка в Celery.
/internal/pipeline/generate — on-demand генерация черновиков по scored-статьям тенанта.
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
from app.config import settings
from app.db.engine import session_scope
from app.db.models import Tenant
from app.db.repositories import (
    ArticleRepository,
    EmailRepository,
    PipelineRunRepository,
    PostRepository,
    tenant_month_spend,
)
from app.metering import TRIAL_DEFAULT_DRAFTS_LIMIT, budget_exceeded, month_start_utc
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


class GenerateRequest(BaseModel):
    tenant_id: str
    article_ids: list[str] | None = None


class GenerateResponse(BaseModel):
    tenant_id: str
    queued: bool
    count: int
    detail: str
    budget_exceeded: bool = False


@router.post("/internal/pipeline/generate", response_model=GenerateResponse)
def generate_drafts(req: GenerateRequest) -> GenerateResponse:
    """Сгенерировать черновики по прошедшим отбор статьям тенанта (on-demand).

    По умолчанию — весь scored-хвост; опц. фильтр article_ids для курируемой генерации из дашборда.
    """
    tenant_uuid = uuid.UUID(req.tenant_id)
    article_uuids = [uuid.UUID(a) for a in req.article_ids] if req.article_ids is not None else None
    with session_scope() as session:
        tenant = session.get(Tenant, tenant_uuid)
        budget = tenant.ai_budget_usd_month if tenant is not None else None
        spent = tenant_month_spend(session, tenant_uuid, since=month_start_utc())
        count = len(
            ArticleRepository.scored_articles(session, tenant_uuid, article_ids=article_uuids)
        )
        trial_drafts_hit = _trial_drafts_exhausted(session, tenant)

    # Hard-cap: гейтим только генерацию (дорогая стадия). Скоринг/ingestion не трогаем.
    if budget_exceeded(spent, budget):
        return GenerateResponse(
            tenant_id=req.tenant_id,
            queued=False,
            count=count,
            detail="budget_exceeded",
            budget_exceeded=True,
        )

    # Триал: value-fence по числу драфтов (первый достигнутый лимит триала блокирует генерацию).
    if trial_drafts_hit:
        return GenerateResponse(
            tenant_id=req.tenant_id,
            queued=False,
            count=count,
            detail="trial_drafts_exhausted",
            budget_exceeded=True,
        )

    if count == 0:
        return GenerateResponse(
            tenant_id=req.tenant_id, queued=False, count=0, detail="no scored articles to draft"
        )

    try:
        from app.worker.tasks import run_tenant_generation

        run_tenant_generation.delay(req.tenant_id, req.article_ids)
        queued = True
        detail = "queued"
    except Exception as exc:
        queued = False
        detail = f"not queued: {exc}"

    return GenerateResponse(tenant_id=req.tenant_id, queued=queued, count=count, detail=detail)


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
    except Exception:
        # Не эхоим сырой текст исключения: он может раскрыть внутренний хост/порт/статус
        # при SSRF-пробе. Наружу — только opaque-код.
        return {"ok": False, "error": "fetch_error"}

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


@router.get("/internal/adapters")
def list_adapters() -> dict:
    """Описание адаптеров источников: config_schema (секреты вырезаны) + capabilities.

    UI рисует форму источника из JSON-схемы. Метод describe() уже вырезает секрет-поля.
    """
    return {"adapters": REGISTRY.describe()}


# ─────────────────────────────────────────── Email (M6.3): welcome, вебхук Resend, отписка
# Вебхук/отписка приходят снаружи и проксируются web-сервисом на этот internal-эндпоинт (web —
# единственный внешне доступный сервис). Логика suppression/prefs и верификация подписи — здесь.


class WelcomeRequest(BaseModel):
    user_id: str
    tenant_id: str
    email: str
    locale: str = "en"


@router.post("/internal/notify/welcome")
def notify_welcome(req: WelcomeRequest) -> dict:
    """Поставить welcome-письмо в очередь после регистрации (best-effort, не блокирует web)."""
    try:
        from app.worker.tasks import send_welcome_email

        send_welcome_email.delay(req.user_id, req.tenant_id, req.email, req.locale)
        return {"queued": True}
    except Exception as exc:
        return {"queued": False, "detail": str(exc)}


class EmailWebhookRequest(BaseModel):
    payload: str
    headers: dict[str, str]


@router.post("/internal/email/webhook")
def email_webhook(req: EmailWebhookRequest) -> dict:
    """Вебхук Resend (Svix-подпись по сырому телу). bounce/complaint -> suppression."""
    if not settings.resend_webhook_secret:
        return {"ok": False, "error": "not_configured"}
    from svix.webhooks import Webhook, WebhookVerificationError

    try:
        event = Webhook(settings.resend_webhook_secret).verify(req.payload, req.headers)
    except WebhookVerificationError:
        return {"ok": False, "error": "invalid_signature"}

    event_type = event.get("type")
    data = event.get("data") or {}
    to = data.get("to")
    email_addr = to[0] if isinstance(to, list) and to else (to if isinstance(to, str) else None)
    if event_type in ("email.bounced", "email.complained") and email_addr:
        reason = "complaint" if event_type == "email.complained" else "bounce"
        with session_scope() as session:
            EmailRepository.add_suppression(
                session,
                email_norm=email_addr.strip().lower(),
                reason=reason,
                source_event_id=event.get("id"),
            )
    return {"ok": True}


class UnsubscribeRequest(BaseModel):
    token: str


@router.post("/internal/email/unsubscribe")
def email_unsubscribe(req: UnsubscribeRequest) -> dict:
    """Отписка от digest по токену (one-click). Идемпотентно."""
    try:
        token = uuid.UUID(req.token)
    except ValueError:
        return {"ok": False, "error": "invalid_token"}
    with session_scope() as session:
        found = EmailRepository.unsubscribe_by_token(session, token)
    return {"ok": found}


def _trial_drafts_exhausted(session, tenant) -> bool:
    """Достигнут ли лимит драфтов триала. Вне триала (subscription_status!='trialing') — нет."""
    if tenant is None or tenant.subscription_status != "trialing":
        return False
    limit = (
        tenant.trial_drafts_limit
        if tenant.trial_drafts_limit is not None
        else TRIAL_DEFAULT_DRAFTS_LIMIT
    )
    return PostRepository.count_posts(session, tenant.id) >= limit


def _tenant_timezone(tenant_id: str | None) -> str:
    if not tenant_id:
        return "UTC"
    try:
        with session_scope() as session:
            tenant = session.get(Tenant, uuid.UUID(tenant_id))
            return tenant.timezone if tenant is not None else "UTC"
    except Exception:
        return "UTC"
