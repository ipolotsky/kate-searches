"""Репозитории записи в БД. Пока — только зеркало стоимости LLM (ai_usage)."""

import uuid

from sqlalchemy.orm import Session

from app.db.models import AiUsage


def insert_ai_usage(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    stage: str,
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_usd: float,
    request_id: str | None,
) -> AiUsage:
    row = AiUsage(
        tenant_id=tenant_id,
        user_id=user_id,
        stage=stage,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        request_id=request_id,
    )
    session.add(row)
    session.flush()
    return row
