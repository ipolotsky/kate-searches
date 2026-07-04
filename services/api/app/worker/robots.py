"""robots.txt-политика с кэшем в Redis (TTL).

robots.txt кэшируется по хосту. 4xx (нет файла) -> разрешаем всё. 5xx/таймаут -> политика
fail_open (по умолчанию разрешаем фиды с троттлингом; ужесточить для скрапера настройкой).
"""

from collections.abc import Callable
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from app.config import settings

_MISS = "\x00miss"


def _download_robots(host_root: str, timeout: float) -> tuple[int, str]:
    import httpx

    try:
        response = httpx.get(
            f"{host_root}/robots.txt",
            headers={"User-Agent": settings.user_agent},
            timeout=timeout,
            follow_redirects=True,
        )
        return response.status_code, response.text
    except httpx.HTTPError:
        return 0, ""


class RobotsPolicy:
    def __init__(
        self,
        redis_client=None,
        *,
        user_agent: str | None = None,
        fail_open: bool = True,
        download: Callable[[str, float], tuple[int, str]] = _download_robots,
    ) -> None:
        self._redis = redis_client
        self.user_agent = user_agent or settings.user_agent
        self.fail_open = fail_open
        self._download = download

    @property
    def redis(self):
        if self._redis is None:
            import redis

            self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        if not parts.scheme or not parts.netloc:
            return self.fail_open
        host_root = f"{parts.scheme}://{parts.netloc}"
        key = f"robots:{parts.netloc}"

        cached = self.redis.get(key)
        if cached is None:
            status, body = self._download(host_root, settings.fetch_timeout_seconds)
            if status == 0 or status >= 500:
                # недоступно / серверная ошибка: тело — не robots-правила, не парсим его.
                # fail_open -> разрешаем (кэш "" на короткий TTL), иначе запрещаем (кэш _MISS).
                cached = "" if self.fail_open else _MISS
                self.redis.setex(key, 300, cached)
            elif 400 <= status < 500:
                cached = ""
                self.redis.setex(key, settings.robots_cache_ttl_seconds, cached)
            else:
                cached = body
                self.redis.setex(key, settings.robots_cache_ttl_seconds, cached)

        if cached == _MISS:
            return False
        parser = RobotFileParser()
        parser.parse(cached.splitlines())
        return parser.can_fetch(self.user_agent, url)
