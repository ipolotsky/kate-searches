"""Чистые хелперы метеринга/бюджета (без БД, unit-тестируемые).

Расход считаем compute-on-read из ai_usage за текущий календарный месяц (UTC).
Hard-cap энфорсит только генерацию (дорогая стадия), скоринг/ingestion не гейтятся.
"""

from datetime import UTC, datetime
from decimal import Decimal


class BudgetExceededError(Exception):
    """LLM-вызов заблокирован: месячный бюджет тенанта исчерпан (строгий hard-cap)."""


def month_start_utc(now: datetime | None = None) -> datetime:
    """Начало текущего календарного месяца в UTC (граница окна расхода)."""
    reference = now if now is not None else datetime.now(UTC)
    return datetime(reference.year, reference.month, 1, tzinfo=UTC)


def period_key_utc(now: datetime | None = None) -> str:
    """Ключ периода 'YYYY-MM' (UTC) для леджера — даёт бесплатный месячный сброс."""
    reference = now if now is not None else datetime.now(UTC)
    return f"{reference.year:04d}-{reference.month:02d}"


def budget_exceeded(spent: Decimal, budget: Decimal | None) -> bool:
    """Достигнут ли месячный бюджет. Без бюджета (None) — не блокируем."""
    return budget is not None and spent >= budget


# Консервативная верхняя оценка стоимости одного вызова стадии. Резервируется ДО вызова
# (когда факт ещё неизвестен), затем сверяется на фактическую стоимость после ответа.
STAGE_COST_ESTIMATE: dict[str, Decimal] = {
    "score": Decimal("0.002"),
    "draft": Decimal("0.06"),
}
DEFAULT_COST_ESTIMATE = Decimal("0.01")


def estimate_for(stage: str) -> Decimal:
    return STAGE_COST_ESTIMATE.get(stage, DEFAULT_COST_ESTIMATE)
