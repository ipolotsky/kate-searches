"""Чистые хелперы метеринга/бюджета (без БД, unit-тестируемые).

Расход считаем compute-on-read из ai_usage за текущий календарный месяц (UTC).
Hard-cap энфорсит только генерацию (дорогая стадия), скоринг/ingestion не гейтятся.
"""

from datetime import UTC, datetime
from decimal import Decimal


def month_start_utc(now: datetime | None = None) -> datetime:
    """Начало текущего календарного месяца в UTC (граница окна расхода)."""
    reference = now if now is not None else datetime.now(UTC)
    return datetime(reference.year, reference.month, 1, tzinfo=UTC)


def budget_exceeded(spent: Decimal, budget: Decimal | None) -> bool:
    """Достигнут ли месячный бюджет. Без бюджета (None) — не блокируем."""
    return budget is not None and spent >= budget
