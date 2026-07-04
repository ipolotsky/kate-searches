"""Платный fallback через Firecrawl API. Каждый вызов стоит денег — включается только
когда caskад допускает платные fetcher-ы (не в dry-run теста источника)."""

from app.config import settings
from app.fetch.base import FetchedPage

_API_URL = "https://api.firecrawl.dev/v1/scrape"


class FirecrawlFetcher:
    name = "firecrawl"
    is_paid = True
    requires_js = False

    def fetch_html(
        self, url: str, *, render_js: bool = False, timeout: float | None = None
    ) -> FetchedPage:
        import httpx

        if not settings.firecrawl_api_key:
            return FetchedPage(final_url=url, fetcher=self.name, error="no_firecrawl_key")

        headers = {
            "Authorization": f"Bearer {settings.firecrawl_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"url": url, "formats": ["html"]}
        try:
            response = httpx.post(
                _API_URL,
                headers=headers,
                json=payload,
                timeout=timeout or settings.fetch_timeout_seconds * 3,
            )
            response.raise_for_status()
            data = response.json().get("data", {})
        except httpx.HTTPError as exc:
            return FetchedPage(final_url=url, fetcher=self.name, error=str(exc))

        html = data.get("html") or data.get("rawHtml") or ""
        return FetchedPage(
            html=html,
            status=200 if html else 0,
            final_url=data.get("metadata", {}).get("sourceURL", url),
            fetcher=self.name,
            cost_usd=settings.firecrawl_cost_per_call_usd,
        )
