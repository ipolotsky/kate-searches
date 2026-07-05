"""Единая точка всех LLM-вызовов.

Instructor (structured output) поверх LiteLLM (роутинг + бюджеты), трейс в Langfuse
и запись стоимости per-tenant в ai_usage. Модель роутится по стадии в pipeline/*.
"""

import os
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db.engine import session_scope
from app.db.repositories import insert_ai_usage

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
    import instructor
    import litellm

    _configure_provider_keys()
    _configure_langfuse()
    trace_id = str(uuid.uuid4())
    client = instructor.from_litellm(litellm.completion)
    result, completion = client.chat.completions.create_with_completion(
        model=model,
        messages=messages,
        response_model=response_model,
        max_tokens=max_tokens,
        metadata=_metadata(tenant_id=tenant_id, stage=stage, user_id=user_id, trace_id=trace_id),
        **_proxy_params(),
    )
    _record_usage(
        tenant_id=tenant_id,
        user_id=user_id,
        stage=stage,
        model=model,
        completion=completion,
        request_id=trace_id,
        pipeline_run_id=pipeline_run_id,
        session_factory=session_factory,
    )
    return result


def _proxy_params() -> dict:
    if not settings.litellm_base_url:
        return {}
    return {"api_base": settings.litellm_base_url, "api_key": settings.litellm_master_key}


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
) -> None:
    """Записать стоимость вызова в ai_usage (зеркало Langfuse для апселла/отчётов)."""
    import litellm

    try:
        cost = float(litellm.completion_cost(completion_response=completion) or 0.0)
    except Exception:
        cost = 0.0
    usage = getattr(completion, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", None)
    output_tokens = getattr(usage, "completion_tokens", None)
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
