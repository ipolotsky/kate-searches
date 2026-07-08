"""Единая точка всех LLM-вызовов.

Instructor (structured output) поверх LiteLLM (роутинг + бюджеты), трейс в Langfuse
и запись стоимости per-tenant в ai_usage. Модель роутится по стадии в pipeline/*.
"""

import os
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db.engine import session_scope
from app.db.models import Tenant
from app.db.repositories import insert_ai_usage, reserve_budget, settle_budget
from app.metering import (
    BudgetExceededError,
    estimate_for,
    period_key_utc,
    stage_is_hard_capped,
)

SessionFactory = Callable[[], AbstractContextManager[Session]]


def structured_completion[T: BaseModel](
    *,
    model: str,
    messages: list[dict],
    response_model: type[T],
    tenant_id: str,
    stage: str,
    user_id: str | None = None,
    pipeline_run_id: uuid.UUID | str | None = None,
    max_tokens: int = 2048,
    session_factory: SessionFactory = session_scope,
) -> T:
    """Вызвать LLM и вернуть валидированный Pydantic-объект, записав стоимость в ai_usage."""
    result, _ = structured_completion_with_usage(
        model=model,
        messages=messages,
        response_model=response_model,
        tenant_id=tenant_id,
        stage=stage,
        user_id=user_id,
        pipeline_run_id=pipeline_run_id,
        max_tokens=max_tokens,
        session_factory=session_factory,
    )
    return result


def structured_completion_with_usage[T: BaseModel](
    *,
    model: str,
    messages: list[dict],
    response_model: type[T],
    tenant_id: str,
    stage: str,
    user_id: str | None = None,
    pipeline_run_id: uuid.UUID | str | None = None,
    max_tokens: int = 2048,
    session_factory: SessionFactory = session_scope,
) -> tuple[T, float]:
    """Как structured_completion, но дополнительно возвращает стоимость вызова в USD.

    Нужна стадиям, которые пишут стоимость в свою таблицу (posts.ai_cost_usd), не только в ai_usage.
    """
    import instructor
    import litellm

    _configure_provider_keys()
    _configure_langfuse()

    # Строгий hard-cap: атомарно резервируем оценку под бюджет ДО вызова. Если исчерпан — блок.
    reservation = _reserve_budget(tenant_id=tenant_id, stage=stage, session_factory=session_factory)

    trace_id = str(uuid.uuid4())
    client = instructor.from_litellm(litellm.completion)
    try:
        result, completion = client.chat.completions.create_with_completion(
            model=model,
            messages=messages,
            response_model=response_model,
            max_tokens=max_tokens,
            metadata=_metadata(
                tenant_id=tenant_id, stage=stage, user_id=user_id, trace_id=trace_id
            ),
            **_proxy_params(),
        )
    except Exception:
        # Вызов не состоялся — денег не потратили: рефанд резерва.
        _refund_reservation(
            tenant_id=tenant_id, reservation=reservation, session_factory=session_factory
        )
        raise

    # Вызов уже оплачен провайдеру. Дальнейший bookkeeping (запись ai_usage, сверка резерва)
    # строго best-effort: его сбой НЕ должен пробрасываться, иначе generate_draft_run поймает
    # исключение, откатит claim (drafting -> scored) и статья перегенерится — двойное списание.
    cost = _record_usage(
        tenant_id=tenant_id,
        user_id=user_id,
        stage=stage,
        model=model,
        completion=completion,
        request_id=trace_id,
        pipeline_run_id=pipeline_run_id,
        session_factory=session_factory,
    )
    try:
        # Сверяем резерв на факт (резерв оставляем, если сверка упала — консервативно,
        # расхождение поправит фоновая реконсиляция леджера).
        _settle_reservation(
            tenant_id=tenant_id,
            reservation=reservation,
            cost=cost,
            session_factory=session_factory,
        )
    except Exception:
        pass
    return result, cost


def _proxy_params() -> dict:
    if not settings.litellm_base_url:
        return {}
    return {"api_base": settings.litellm_base_url, "api_key": settings.litellm_master_key}


def _reserve_budget(
    *, tenant_id: str, stage: str, session_factory: SessionFactory
) -> tuple[str, Decimal] | None:
    """Зарезервировать оценку стоимости стадии под месячный бюджет тенанта (строгий hard-cap).

    None — бюджета нет (не гейтим). Raise BudgetExceededError — бюджет исчерпан. Резерв коммитится
    своей транзакцией, чтобы конкурентные вызовы видели его атомарно (нет TOCTOU-гонки).
    """
    # Hard-cap энфорсит только дорогую стадию (draft). Дешёвый скоринг/ingestion через ledger
    # не гоняем: иначе при добитом бюджете score падал бы в BudgetExceededError и статьи
    # застревали бы в 'extracted' без пере-скоринга.
    if not stage_is_hard_capped(stage):
        return None
    with session_factory() as session:
        tenant = session.get(Tenant, uuid.UUID(str(tenant_id)))
        if tenant is None or tenant.ai_budget_usd_month is None:
            return None
        budget = tenant.ai_budget_usd_month
        period = period_key_utc()
        estimate = estimate_for(stage)
        if budget <= 0 or not reserve_budget(
            session, tenant.id, period=period, estimate=estimate, budget=budget
        ):
            raise BudgetExceededError(f"monthly AI budget exhausted for tenant {tenant_id}")
    return period, estimate


def _refund_reservation(
    *, tenant_id: str, reservation: tuple[str, Decimal] | None, session_factory: SessionFactory
) -> None:
    """Вернуть резерв (вызов не состоялся — денег не потратили)."""
    if reservation is None:
        return
    period, estimate = reservation
    with session_factory() as session:
        settle_budget(session, uuid.UUID(str(tenant_id)), period=period, delta=-estimate)


def _settle_reservation(
    *,
    tenant_id: str,
    reservation: tuple[str, Decimal] | None,
    cost: float,
    session_factory: SessionFactory,
) -> None:
    """Свести резерв к фактической стоимости (delta = факт - оценка)."""
    if reservation is None:
        return
    period, estimate = reservation
    with session_factory() as session:
        settle_budget(
            session, uuid.UUID(str(tenant_id)), period=period, delta=Decimal(str(cost)) - estimate
        )


def _metadata(*, tenant_id: str, stage: str, user_id: str | None, trace_id: str) -> dict:
    metadata: dict = {
        "trace_id": trace_id,
        "tenant_id": tenant_id,
        "stage": stage,
        "tags": [f"tenant:{tenant_id}", f"stage:{stage}"],
    }
    if user_id is not None:
        metadata["trace_user_id"] = user_id
    return metadata


def _configure_provider_keys() -> None:
    """Прокинуть ключи провайдеров из settings в os.environ для litellm (прямые вызовы).

    pydantic-settings читает .env в объект settings, но НЕ экспортирует в окружение, а litellm
    берёт ключи провайдеров из os.environ. setdefault уважает уже заданный извне ключ (live-тесты).
    """
    for env_name, value in (
        ("OPENAI_API_KEY", settings.openai_api_key),
        ("GEMINI_API_KEY", settings.gemini_api_key),
        ("ANTHROPIC_API_KEY", settings.anthropic_api_key),
    ):
        if value and not os.environ.get(env_name):
            os.environ[env_name] = value


def _configure_langfuse() -> None:
    if not settings.langfuse_enabled:
        return
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return
    import litellm

    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)
    callbacks = litellm.success_callback or []
    if "langfuse" not in callbacks:
        litellm.success_callback = [*callbacks, "langfuse"]


def _record_usage(
    *,
    tenant_id: str,
    user_id: str | None,
    stage: str,
    model: str,
    completion: object,
    request_id: str,
    pipeline_run_id: uuid.UUID | str | None,
    session_factory: SessionFactory,
) -> float:
    """Записать стоимость вызова в ai_usage (зеркало Langfuse для апселла). Вернуть стоимость."""
    import litellm

    try:
        cost = float(litellm.completion_cost(completion_response=completion) or 0.0)
    except Exception:
        cost = 0.0
    usage = getattr(completion, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", None)
    output_tokens = getattr(usage, "completion_tokens", None)
    try:
        with session_factory() as session:
            insert_ai_usage(
                session,
                tenant_id=uuid.UUID(str(tenant_id)),
                user_id=uuid.UUID(str(user_id)) if user_id is not None else None,
                stage=stage,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                request_id=request_id,
                pipeline_run_id=(
                    uuid.UUID(str(pipeline_run_id)) if pipeline_run_id is not None else None
                ),
            )
    except Exception:
        # ai_usage — зеркало для отчётности/апселла; его сбой не отменяет уже оплаченный
        # вызов. Возвращаем посчитанную стоимость, чтобы вызывающий сохранил её в posts.
        pass
    return cost
