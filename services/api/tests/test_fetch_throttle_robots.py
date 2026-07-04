"""Fetcher-каскад, robots-политика и token-bucket троттлинг на фейковом времени."""

import fakeredis
import pytest

from app.fetch.base import FetchedPage, is_usable, looks_blocked
from app.fetch.cascade import CascadeFetcher
from app.worker.robots import RobotsPolicy
from app.worker.throttle import RateLimiter, refill_consume

# ─────────────────────────────────────────── Fetcher-каскад


class _FakeFetcher:
    def __init__(self, name, page, *, is_paid=False, requires_js=False):
        self.name = name
        self._page = page
        self.is_paid = is_paid
        self.requires_js = requires_js
        self.calls = 0

    def fetch_html(self, url, *, render_js=False, timeout=None):
        self.calls += 1
        return self._page.model_copy(update={"fetcher": self.name})


def _page(html="", status=200, error=None):
    return FetchedPage(html=html, status=status, error=error, final_url="https://x.test")


def test_cascade_returns_first_usable() -> None:
    good = _FakeFetcher("httpx", _page(html="x" * 800))
    never = _FakeFetcher("firecrawl", _page(html="y" * 800), is_paid=True)
    cascade = CascadeFetcher([good, never], allow_paid=True, min_chars=500)
    result = cascade.fetch_html("https://x.test/a")
    assert result.fetcher == "httpx"
    assert never.calls == 0


def test_cascade_escalates_on_thin_body() -> None:
    thin = _FakeFetcher("httpx", _page(html="short"))
    rich = _FakeFetcher("firecrawl", _page(html="z" * 800), is_paid=True)
    cascade = CascadeFetcher([thin, rich], allow_paid=True, min_chars=500)
    result = cascade.fetch_html("https://x.test/a")
    assert result.fetcher == "firecrawl"
    assert thin.calls == 1


def test_cascade_skips_paid_when_not_allowed() -> None:
    thin = _FakeFetcher("httpx", _page(html="short"))
    paid = _FakeFetcher("firecrawl", _page(html="z" * 800), is_paid=True)
    cascade = CascadeFetcher([thin, paid], allow_paid=False, min_chars=500)
    result = cascade.fetch_html("https://x.test/a")
    assert paid.calls == 0
    assert result.fetcher == "httpx"


def test_cascade_skips_js_fetcher_without_render_js() -> None:
    js_only = _FakeFetcher("crawl4ai", _page(html="z" * 800), requires_js=True)
    plain = _FakeFetcher("httpx", _page(html="short"))
    cascade = CascadeFetcher([plain, js_only], allow_paid=False, min_chars=500)
    cascade.fetch_html("https://x.test/a", render_js=False)
    assert js_only.calls == 0


def test_looks_blocked_detects_antibot() -> None:
    assert looks_blocked(_page(html="please solve the captcha", status=200)) is True
    assert looks_blocked(_page(status=403)) is True
    assert is_usable(_page(html="clean content " * 50, status=200), 100) is True


# ─────────────────────────────────────────── Token-bucket


def test_refill_consume_pure() -> None:
    tokens, allowed, retry = refill_consume(1.0, 0.0, 0.0, rate_per_sec=1.0, capacity=1.0)
    assert allowed is True and tokens == 0.0
    tokens, allowed, retry = refill_consume(0.0, 0.0, 0.0, rate_per_sec=1.0, capacity=1.0)
    assert allowed is False and retry == pytest.approx(1.0)


def test_rate_limiter_blocks_then_refills() -> None:
    clock = {"t": 1000.0}
    limiter = RateLimiter(fakeredis.FakeRedis(decode_responses=True), clock=lambda: clock["t"])
    first = limiter.acquire("news.test", rpm=1)
    assert first.allowed is True
    second = limiter.acquire("news.test", rpm=1)
    assert second.allowed is False
    assert second.retry_after == pytest.approx(60.0, abs=1.0)
    clock["t"] += 61.0
    third = limiter.acquire("news.test", rpm=1)
    assert third.allowed is True


def test_rate_limiter_per_host_isolated() -> None:
    clock = {"t": 0.0}
    limiter = RateLimiter(fakeredis.FakeRedis(decode_responses=True), clock=lambda: clock["t"])
    assert limiter.acquire("a.test", rpm=1).allowed is True
    assert limiter.acquire("b.test", rpm=1).allowed is True


# ─────────────────────────────────────────── robots.txt


def _robots_policy(status, body, **kw):
    return RobotsPolicy(
        fakeredis.FakeRedis(decode_responses=True),
        download=lambda host, timeout: (status, body),
        **kw,
    )


def test_robots_allow_and_disallow() -> None:
    policy = _robots_policy(200, "User-agent: *\nDisallow: /private\n")
    assert policy.allowed("https://x.test/public") is True
    assert policy.allowed("https://x.test/private/p") is False


def test_robots_404_allows_all() -> None:
    policy = _robots_policy(404, "")
    assert policy.allowed("https://x.test/anything") is True


def test_robots_5xx_fail_open_policy() -> None:
    assert _robots_policy(0, "", fail_open=True).allowed("https://x.test/a") is True
    assert _robots_policy(0, "", fail_open=False).allowed("https://x.test/a") is False


def test_robots_500_does_not_parse_error_body() -> None:
    # 5xx с HTML-телом ошибки: тело — не robots-правила. fail_open -> allow, иначе deny.
    error_body = "<html><body>500 Internal Server Error</body></html>"
    assert _robots_policy(500, error_body, fail_open=True).allowed("https://x.test/a") is True
    assert _robots_policy(503, error_body, fail_open=False).allowed("https://x.test/a") is False
