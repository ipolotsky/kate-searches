from datetime import datetime, timedelta, timezone

from app.pipeline.dedup import canonicalize_url, is_fresh


def test_canonicalize_strips_tracking_and_trailing_slash():
    a = canonicalize_url("https://Example.com/News/Item/?utm_source=x&id=5&fbclid=abc")
    b = canonicalize_url("http://example.com/News/Item?id=5")
    assert a == b
    assert "utm_source" not in a
    assert "fbclid" not in a


def test_canonicalize_lowercases_host_not_path_query():
    assert canonicalize_url("https://EXAMPLE.com/Path") == "https://example.com/Path"


def test_is_fresh_today_true_old_false():
    now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
    assert is_fresh(now - timedelta(hours=5), tz_now=now) is True
    assert is_fresh(now - timedelta(days=3), tz_now=now) is False


def test_is_fresh_handles_naive_datetime():
    now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
    naive = datetime(2026, 6, 30, 9, 0)
    assert is_fresh(naive, tz_now=now) is True
