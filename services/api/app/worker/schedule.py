"""tz-диспетчер: локальная дата тенанта на момент дневного прогона.

Celery beat не умеет per-tenant tz-cron, поэтому heartbeat считает локальное время тенанта.
run_date — ЛОКАЛЬНАЯ дата тенанта, не UTC (иначе ключ идемпотентности разъедется с tz).
"""

from datetime import date, datetime

from app.pipeline.dedup import _safe_zone


def local_run_date_if_due(
    timezone: str, pipeline_hour_local: int, now_utc: datetime
) -> date | None:
    """Локальная дата тенанта, если наступил его час дневного прогона (или позже), иначе None.

    `>=`, а не `==`: (1) на DST spring-forward день настроенный локальный час может быть пропущен
    (03:00 сразу после 01:59) — строгое равенство никогда не сматчится и прогон дня потеряется;
    (2) если воркер простаивал, прогон всё равно заявится позже в тот же локальный день (catch-up).
    Идемпотентный claim_run по (tenant, run_date, mode) гарантирует ровно один прогон в сутки.
    """
    zone = _safe_zone(timezone)
    local_now = now_utc.astimezone(zone)
    if local_now.hour >= pipeline_hour_local:
        return local_now.date()
    return None
