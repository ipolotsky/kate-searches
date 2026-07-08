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

# Строгий hard-cap ledger'а энфорсит только дорогую стадию генерации; скоринг и ingestion
# не гейтятся (см. routes.py, generation-only cap). Прогонять дешёвый скоринг через ledger
# нельзя: при добитом бюджете он падал бы в BudgetExceededError и статьи застревали бы в
# 'extracted' без пере-скоринга. Триальный режим (M6.2) добавит 'score' сюда для триал-тенантов.
HARD_CAPPED_STAGES: frozenset[str] = frozenset({"draft"})


def estimate_for(stage: str) -> Decimal:
    return STAGE_COST_ESTIMATE.get(stage, DEFAULT_COST_ESTIMATE)


def stage_is_hard_capped(stage: str) -> bool:
    return stage in HARD_CAPPED_STAGES
