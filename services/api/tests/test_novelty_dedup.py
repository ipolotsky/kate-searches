"""Новизна по tz/DST и дедуп: simhash round-trip, порог Hamming, priority-тай-брейк."""

from datetime import UTC, datetime

from app.pipeline.dedup import (
    content_hash,
    hamming,
    is_better_canonical,
    is_novel,
    normalize_timezone,
    simhash64,
    to_signed,
    to_unsigned,
)


def test_dateless_never_novel() -> None:
    assert is_novel(None, "UTC", now_utc=datetime(2026, 7, 4, 12, tzinfo=UTC)) is False


def test_novel_today_true_yesterday_false_utc() -> None:
    now = datetime(2026, 7, 4, 12, tzinfo=UTC)
    assert is_novel(datetime(2026, 7, 4, 6, tzinfo=UTC), "UTC", now_utc=now) is True
    assert is_novel(datetime(2026, 7, 3, 23, tzinfo=UTC), "UTC", now_utc=now) is False


def test_novelty_boundary_respects_tenant_timezone() -> None:
    now = datetime(2026, 7, 4, 12, tzinfo=UTC)
    # Лос-Анджелес PDT (UTC-7): полночь 2026-07-04 = 07:00 UTC.
    published_early = datetime(2026, 7, 4, 6, tzinfo=UTC)  # 2026-07-03 23:00 PDT — вчера локально
    published_late = datetime(2026, 7, 4, 8, tzinfo=UTC)  # 2026-07-04 01:00 PDT — сегодня локально
    assert is_novel(published_early, "America/Los_Angeles", now_utc=now) is False
    assert is_novel(published_late, "America/Los_Angeles", now_utc=now) is True
    # Тот же момент для UTC-тенанта проходит гейт (граница = 00:00 UTC).
    assert is_novel(published_early, "UTC", now_utc=now) is True


def test_novelty_boundary_uses_dst_offset() -> None:
    # Берлин в июле — CEST (UTC+2): полночь 2026-07-04 = 2026-07-03 22:00 UTC.
    now = datetime(2026, 7, 4, 0, 30, tzinfo=UTC)
    assert is_novel(datetime(2026, 7, 3, 23, tzinfo=UTC), "Europe/Berlin", now_utc=now) is True
    assert is_novel(datetime(2026, 7, 3, 21, tzinfo=UTC), "Europe/Berlin", now_utc=now) is False


def test_novelty_days_widens_window() -> None:
    now = datetime(2026, 7, 4, 12, tzinfo=UTC)
    two_days_ago = datetime(2026, 7, 2, 12, tzinfo=UTC)
    assert is_novel(two_days_ago, "UTC", now_utc=now) is False
    assert is_novel(two_days_ago, "UTC", now_utc=now, novelty_days=3) is True


def test_backfill_uses_since_not_today() -> None:
    now = datetime(2026, 7, 4, 12, tzinfo=UTC)
    old = datetime(2026, 1, 1, tzinfo=UTC)
    since = datetime(2025, 12, 1, tzinfo=UTC)
    assert is_novel(old, "UTC", now_utc=now, mode="backfill", since=since) is True
    assert (
        is_novel(
            datetime(2025, 11, 1, tzinfo=UTC), "UTC", now_utc=now, mode="backfill", since=since
        )
        is False
    )


def test_lookback_grace_extends_window() -> None:
    now = datetime(2026, 7, 4, 1, tzinfo=UTC)
    just_before_midnight = datetime(2026, 7, 3, 23, tzinfo=UTC)
    assert is_novel(just_before_midnight, "UTC", now_utc=now) is False
    assert is_novel(just_before_midnight, "UTC", now_utc=now, lookback_hours=2) is True


def test_normalize_timezone_fallback() -> None:
    assert normalize_timezone("Europe/Berlin") == "Europe/Berlin"
    assert normalize_timezone("Nonsense/Zone") == "UTC"
    assert normalize_timezone(None) == "UTC"
    assert normalize_timezone("") == "UTC"


def test_invalid_timezone_falls_back_without_crash() -> None:
    now = datetime(2026, 7, 4, 12, tzinfo=UTC)
    assert is_novel(datetime(2026, 7, 4, 6, tzinfo=UTC), "Bogus/Zone", now_utc=now) is True


def test_naive_published_treated_as_utc() -> None:
    now = datetime(2026, 7, 4, 12, tzinfo=UTC)
    naive_today = datetime(2026, 7, 4, 9)
    assert is_novel(naive_today, "UTC", now_utc=now) is True


def test_signed_unsigned_round_trip_boundary_bits() -> None:
    for value in (0, 1, _max := (1 << 64) - 1, 1 << 63, (1 << 63) - 1):
        assert to_unsigned(to_signed(value)) == value
    assert -(1 << 63) <= to_signed(0) <= (1 << 63) - 1
    assert -(1 << 63) <= to_signed((1 << 64) - 1) <= (1 << 63) - 1


_ARTICLE = (
    "The heritage fashion house unveiled its autumn archive collection this morning at a "
    "private showing in Milan. Editors noted the reissued leather jackets and hand stitched "
    "denim pieces that first appeared decades ago. Resale specialists expect strong demand "
    "among collectors who track rare designer items and vintage runway samples across Europe."
)
# Та же копия под другим CMS: другой пробельный/регистровый шум — типичная синдикация.
_ARTICLE_REFORMATTED = ("  \n".join(_ARTICLE.split(". "))).upper() + "   "
_UNRELATED = (
    "The central bank held interest rates steady on Wednesday while economists debated the "
    "outlook for semiconductor exports and industrial output over the coming fiscal quarter, "
    "citing weak consumer spending and volatile energy prices across several major markets."
)


def test_hamming_survives_signed_bigint_storage() -> None:
    ua, ub = simhash64(_ARTICLE), simhash64(_UNRELATED)
    stored_a, stored_b = to_signed(ua), to_signed(ub)
    assert hamming(to_unsigned(stored_a), to_unsigned(stored_b)) == hamming(ua, ub)


def test_simhash_near_for_reformatting_far_for_different() -> None:
    # Переформатирование той же копии остаётся под порогом near-dup.
    assert hamming(simhash64(_ARTICLE), simhash64(_ARTICLE_REFORMATTED)) <= 3
    # Другой текст — далеко за порогом.
    assert hamming(simhash64(_ARTICLE), simhash64(_UNRELATED)) > 3
    # Небольшая правка ближе к оригиналу, чем несвязанный текст.
    minor_edit = _ARTICLE.replace("Milan", "Paris")
    assert hamming(simhash64(_ARTICLE), simhash64(minor_edit)) < hamming(
        simhash64(_ARTICLE), simhash64(_UNRELATED)
    )


def test_simhash_identical_is_zero_distance() -> None:
    t = "Some breaking fashion news about a rare archival piece"
    assert hamming(simhash64(t), simhash64(t)) == 0
    assert simhash64("") == 0


def test_content_hash_ignores_whitespace_and_case() -> None:
    assert content_hash("Hello   World\n") == content_hash("hello world")
    assert content_hash("a") != content_hash("b")


def test_is_better_canonical_priority_then_recency() -> None:
    early = datetime(2026, 7, 4, 6, tzinfo=UTC)
    late = datetime(2026, 7, 4, 8, tzinfo=UTC)
    assert is_better_canonical(5, late, 3, early) is True
    assert is_better_canonical(3, early, 5, late) is False
    assert is_better_canonical(4, early, 4, late) is True
    assert is_better_canonical(4, late, 4, early) is False
    assert is_better_canonical(4, early, 4, early) is False
