"""Единая точка всех LLM-вызовов.

Все вызовы идут отсюда: Instructor (structured output) поверх LiteLLM (роутинг + бюджеты),
с трейсом в Langfuse и записью стоимости per-tenant.

ВАЖНО: это тонкая обёртка. Реальную интеграцию LiteLLM proxy / Langfuse callback
дорабатываем в M0 (см. docs/03_architecture.md §6). Сейчас — рабочий контракт + TODO.
"""

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def structured_completion(
    *,
    model: str,
    messages: list[dict],
    response_model: type[T],
    tenant_id: str,
    stage: str,
    max_tokens: int = 2048,
) -> T:
    """Вызвать LLM и вернуть валидированный Pydantic-объект.

    TODO(M0):
      - подключить instructor.from_litellm(litellm.completion)
      - передавать metadata={tenant_id, stage} для Langfuse-атрибуции
      - писать стоимость в ai_usage (зеркало Langfuse) для апселла/отчётов
      - hard-бюджет per-tenant через LiteLLM virtual key
    """
    import instructor
    import litellm

    client = instructor.from_litellm(litellm.completion)
    result, completion = client.chat.completions.create_with_completion(
        model=model,
        messages=messages,
        response_model=response_model,
        max_tokens=max_tokens,
        metadata={"tenant_id": tenant_id, "stage": stage},
    )
    _record_usage(tenant_id=tenant_id, stage=stage, model=model, completion=completion)
    return result


def _record_usage(*, tenant_id: str, stage: str, model: str, completion) -> None:
    """Записать стоимость вызова. TODO(M0): запись в ai_usage + Langfuse."""
    # litellm считает стоимость локально по таблице цен:
    # cost = litellm.completion_cost(completion_response=completion)
    return None
