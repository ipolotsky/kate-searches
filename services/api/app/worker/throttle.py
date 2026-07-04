"""Per-host token-bucket на Redis (общий для всех тенантов).

rpm берётся из capabilities/config. Логика refill/consume — чистая функция на инъектируемых
часах (тестируется на фейковом времени). Redis держит только tokens+ts на хост.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class AcquireResult:
    allowed: bool
    retry_after: float


def refill_consume(
    tokens: float, last: float, now: float, rate_per_sec: float, capacity: float
) -> tuple[float, bool, float]:
    """Пополнить ведро и попытаться списать один токен."""
    elapsed = max(0.0, now - last)
    tokens = min(capacity, tokens + elapsed * rate_per_sec)
    if tokens >= 1.0:
        return tokens - 1.0, True, 0.0
    deficit = 1.0 - tokens
    retry_after = deficit / rate_per_sec if rate_per_sec > 0 else float("inf")
    return tokens, False, retry_after


class RateLimiter:
    def __init__(self, redis_client=None, *, clock: Callable[[], float] = time.time) -> None:
        # Ведро общее в Redis для всех воркеров/хостов, поэтому часы — wall-clock time.time
        # (сопоставим между NTP-хостами), а не monotonic (per-process, несопоставим).
        # refill_consume клампит elapsed>=0, поэтому редкий обратный NTP-скачок безопасен.
        self._redis = redis_client
        self._clock = clock

    @property
    def redis(self):
        if self._redis is None:
            import redis

            self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    def acquire(self, host: str, rpm: int | None = None) -> AcquireResult:
        rpm = rpm or settings.default_rate_limit_rpm
        capacity = float(max(1, rpm))
        rate = rpm / 60.0
        key = f"throttle:{host}"
        now = self._clock()

        data = self.redis.hgetall(key) or {}
        tokens = float(data.get("tokens", capacity))
        last = float(data.get("ts", now))
        tokens, allowed, retry_after = refill_consume(tokens, last, now, rate, capacity)

        self.redis.hset(key, mapping={"tokens": tokens, "ts": now})
        self.redis.expire(key, settings.robots_cache_ttl_seconds)
        return AcquireResult(allowed=allowed, retry_after=retry_after)

    def wait(self, host: str, rpm: int | None = None, *, max_wait: float = 5.0) -> bool:
        """Блокирующе дождаться токена (с потолком)."""
        result = self.acquire(host, rpm)
        if result.allowed:
            return True
        if result.retry_after <= max_wait:
            time.sleep(result.retry_after)
            return self.acquire(host, rpm).allowed
        return False
