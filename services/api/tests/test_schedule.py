"""tz-диспетчер: run_date — локальная дата тенанта; DST spring-forward не теряет прогон."""

from datetime import UTC, date, datetime

from app.worker.schedule import local_run_date_if_due


def test_due_at_local_hour_utc_tenant() -> None:
    now = datetime(2026, 7, 4, 6, 0, tzinfo=UTC)
    assert local_run_date_if_due("UTC", 6, now) == date(2026, 7, 4)
    # До часа прогона — не due.
    assert local_run_date_if_due("UTC", 7, now) is None


def test_due_uses_local_date_not_utc() -> None:
    # Лос-Анджелес PDT (UTC-7): локальные 06:00 = 13:00 UTC.
    now = datetime(2026, 7, 4, 13, 0, tzinfo=UTC)
    assert local_run_date_if_due("America/Los_Angeles", 6, now) == date(2026, 7, 4)
    # LA 03:00 (10:00 UTC) — раньше часа прогона, не due.
    assert (
        local_run_date_if_due("America/Los_Angeles", 6, datetime(2026, 7, 4, 10, tzinfo=UTC))
        is None
    )


def test_due_is_catch_up_after_hour_same_local_day() -> None:
    # LA 22:00 (05:00 UTC next day) — уже сильно позже 06:00, всё равно due на локальную дату.
    now = datetime(2026, 7, 4, 5, 0, tzinfo=UTC)
    assert local_run_date_if_due("America/Los_Angeles", 6, now) == date(2026, 7, 3)


def test_run_date_is_local_date_across_utc_boundary() -> None:
    # Kiritimati (UTC+14): локальные 06:00 2026-07-05 = 16:00 UTC 2026-07-04.
    now = datetime(2026, 7, 4, 16, 0, tzinfo=UTC)
    run_date = local_run_date_if_due("Pacific/Kiritimati", 6, now)
    assert run_date == date(2026, 7, 5)
    assert run_date != now.date()


def test_dst_spring_forward_hour_not_skipped() -> None:
    # 2026-03-08 в America/New_York час 02:00 пропущен (02:00 -> 03:00). При строгом ==
    # прогон дня терялся бы; при >= первый тик после ямы (NY 03:00 = 07:00 UTC EDT) заявляет день.
    now = datetime(2026, 3, 8, 7, 0, tzinfo=UTC)
    assert local_run_date_if_due("America/New_York", 2, now) == date(2026, 3, 8)


def test_invalid_timezone_falls_back_to_utc() -> None:
    now = datetime(2026, 7, 4, 6, 0, tzinfo=UTC)
    assert local_run_date_if_due("Bogus/Zone", 6, now) == date(2026, 7, 4)
