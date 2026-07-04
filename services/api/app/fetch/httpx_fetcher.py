"""Дефолтный дешёвый fetcher без JS-рендера."""

from app.config import settings
from app.fetch.base import FetchedPage


class HttpxFetcher:
    name = "httpx"
    is_paid = False
    requires_js = False

    def fetch_html(
        self, url: str, *, render_js: bool = False, timeout: float | None = None
    ) -> FetchedPage:
        import httpx

        headers = {"User-Agent": settings.user_agent}
        try:
            response = httpx.get(
                url,
                headers=headers,
                timeout=timeout or settings.fetch_timeout_seconds,
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            return FetchedPage(final_url=url, fetcher=self.name, error=str(exc))
        return FetchedPage(
            html=response.text,
            status=response.status_code,
            final_url=str(response.url),
            fetcher=self.name,
        )
