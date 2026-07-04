"""Классы ошибок ingestion. Transient ретраятся, permanent — нет."""


class TransientFetchError(Exception):
    """Временная ошибка (сеть, 5xx, таймаут) — задача ретраится с backoff."""


class PermanentFetchError(Exception):
    """Неисправимая ошибка (robots-deny, 404, parse) — без ретрая, пишется в health источника."""
