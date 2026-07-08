"""JS-рендер fetcher за optional-extra [scraper]. Ленивый импорт: без пакета
возвращает ошибку, каскад падает на следующий fetcher. `make test` не тянет playwright."""

from app.config import settings
from app.fetch.base import FetchedPage


class Crawl4aiFetcher:
    name = "crawl4ai"
    is_paid = False
    requires_js = True

    def fetch_html(
        self, url: str, *, render_js: bool = True, timeout: float | None = None
    ) -> FetchedPage:
        try:
            import asyncio

            from crawl4ai import AsyncWebCrawler
        except ImportError:
            return FetchedPage(final_url=url, fetcher=self.name, error="crawl4ai_not_installed")

        from app.fetch.guard import BlockedUrlError, assert_public_url

        try:
            assert_public_url(url)
        except BlockedUrlError:
            return FetchedPage(final_url=url, fetcher=self.name, error="blocked_url")

        async def _run() -> FetchedPage:
            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.arun(
                    url=url, page_timeout=int((timeout or settings.fetch_timeout_seconds) * 1000)
                )
            html = getattr(result, "html", "") or getattr(result, "cleaned_html", "") or ""
            status = 200 if getattr(result, "success", False) else 0
            return FetchedPage(
                html=html,
                status=status,
                final_url=getattr(result, "url", url),
                fetcher=self.name,
            )

        try:
            page = asyncio.run(_run())
        except Exception as exc:
            return FetchedPage(final_url=url, fetcher=self.name, error=str(exc))

        # Headless-браузер сам следует редиректам и резолвит DNS — guard внутрь не протолкнуть.
        # Пост-проверка: если финальный URL резолвится в непубличный адрес (редирект в приватную
        # сеть), отбрасываем контент, чтобы не сохранить ответ внутреннего сервиса. Полная защита —
        # egress-фильтр на сетевом уровне (RFC1918/link-local/loopback), см. docs/08.
        try:
            assert_public_url(page.final_url)
        except BlockedUrlError:
            return FetchedPage(final_url=page.final_url, fetcher=self.name, error="blocked_url")
        return page
