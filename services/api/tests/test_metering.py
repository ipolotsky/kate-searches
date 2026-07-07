from datetime import UTC, datetime
from decimal import Decimal

from app.metering import budget_exceeded, month_start_utc


def test_month_start_utc_truncates_to_first_of_month():
    result = month_start_utc(datetime(2026, 7, 6, 13, 45, tzinfo=UTC))
    assert result == datetime(2026, 7, 1, tzinfo=UTC)


def test_month_start_utc_january_boundary():
    result = month_start_utc(datetime(2026, 1, 31, 23, 59, 59, tzinfo=UTC))
    assert result == datetime(2026, 1, 1, tzinfo=UTC)


def test_month_start_utc_december_boundary():
    result = month_start_utc(datetime(2026, 12, 15, tzinfo=UTC))
    assert result == datetime(2026, 12, 1, tzinfo=UTC)


def test_budget_exceeded_none_budget_never_blocks():
    assert budget_exceeded(Decimal("999"), None) is False


def test_budget_exceeded_at_boundary_blocks():
    assert budget_exceeded(Decimal("10"), Decimal("10")) is True


def test_budget_exceeded_below_budget_allows():
    assert budget_exceeded(Decimal("9.99"), Decimal("10")) is False


def test_budget_exceeded_over_budget_blocks():
    assert budget_exceeded(Decimal("10.01"), Decimal("10")) is True
