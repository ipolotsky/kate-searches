"""Контракт HTML-fetcher и сигнал качества страницы."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

_ANTIBOT_MARKERS = (
    "captcha",
    "cf-browser-verification",
    "access denied",
    "are you a human",
    "enable javascript and cookies",
    "request unsuccessful",
)


class FetchedPage(BaseModel):
    html: str = ""
    status: int = 0
    final_url: str = ""
    from_cache: bool = False
    fetcher: str = ""
    cost_usd: float = 0.0
    error: str | None = None


@runtime_checkable
class HtmlFetcher(Protocol):
    name: str
    is_paid: bool
    requires_js: bool

    def fetch_html(
        self, url: str, *, render_js: bool = False, timeout: float | None = None
    ) -> FetchedPage: ...


def looks_blocked(page: FetchedPage) -> bool:
    if page.status in (401, 403, 429):
        return True
    lowered = page.html[:4000].lower()
    return any(marker in lowered for marker in _ANTIBOT_MARKERS)


def is_usable(page: FetchedPage, min_chars: int) -> bool:
    """Страница пригодна: успех, непустое тело нужной длины, без анти-бот сигнала."""
    if page.error:
        return False
    if not (200 <= page.status < 300):
        return False
    if looks_blocked(page):
        return False
    return len(page.html.strip()) >= min_chars
