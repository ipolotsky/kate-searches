"""Egress-guard против SSRF: схема, приватные/link-local/loopback/reserved цели, DNS-ошибка."""

import socket

import pytest

from app.fetch.guard import BlockedUrlError, assert_public_url


def _resolve_to(ip: str):
    def inner(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]

    return inner


def test_blocks_non_http_scheme() -> None:
    for url in ("file:///etc/passwd", "gopher://x/", "ftp://host/"):
        with pytest.raises(BlockedUrlError):
            assert_public_url(url)


def test_blocks_missing_host() -> None:
    with pytest.raises(BlockedUrlError):
        assert_public_url("http:///path")


@pytest.mark.parametrize("ip", ["127.0.0.1", "169.254.169.254", "10.0.0.5", "192.168.1.1", "::1"])
def test_blocks_non_public_targets(monkeypatch, ip: str) -> None:
    monkeypatch.setattr("app.fetch.guard.socket.getaddrinfo", _resolve_to(ip))
    with pytest.raises(BlockedUrlError):
        assert_public_url("http://internal.example/")


def test_allows_public_target(monkeypatch) -> None:
    monkeypatch.setattr("app.fetch.guard.socket.getaddrinfo", _resolve_to("8.8.8.8"))
    assert_public_url("https://example.com/feed")


def test_resolve_public_pins_first_public_ip(monkeypatch) -> None:
    from app.fetch.guard import _resolve_public

    monkeypatch.setattr("app.fetch.guard.socket.getaddrinfo", _resolve_to("8.8.8.8"))
    host, ip = _resolve_public("https://example.com/feed")
    assert host == "example.com"
    assert ip == "8.8.8.8"  # коннект пойдёт на этот IP, не резолвим повторно


def test_blocks_on_dns_failure(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise OSError("nxdomain")

    monkeypatch.setattr("app.fetch.guard.socket.getaddrinfo", boom)
    with pytest.raises(BlockedUrlError):
        assert_public_url("http://does-not-resolve.invalid/")


def test_httpx_fetcher_returns_blocked_url_for_private(monkeypatch) -> None:
    from app.fetch.httpx_fetcher import HttpxFetcher

    monkeypatch.setattr("app.fetch.guard.socket.getaddrinfo", _resolve_to("127.0.0.1"))
    page = HttpxFetcher().fetch_html("http://localhost:8000/latest/meta-data")
    assert page.error == "blocked_url"
    assert not page.html


def test_rss_adapter_blocks_private(monkeypatch) -> None:
    from app.adapters.base import FetchRequest
    from app.adapters.rss import RssAdapter

    monkeypatch.setattr("app.fetch.guard.socket.getaddrinfo", _resolve_to("169.254.169.254"))
    result = RssAdapter().fetch(
        FetchRequest(source={"url": "http://169.254.169.254/latest/", "config": {}}, state={})
    )
    assert result.items == []
    assert "blocked_url" in result.warnings
