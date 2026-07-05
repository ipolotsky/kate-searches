"""Топология ingestion: линейный DAG с fan-out/fan-in и post-extract барьером.

Стадии реализованы как чистые sync-функции (session_scope внутри) — детерминированный
барьер для E2E и переиспользование эндпоинтом. Celery-задачи — тонкие обёртки: продакшен
concurrency через chord(group(extract))(dedup_and_score) и chord(group(score))(finalize_run),
барьеры гарантируют, что дедуп видит финальные тела, а скоринг — только выживших после дедупа.
tenant_id всегда берётся из строки sources (защита кросс-тенант записи).
"""

import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import select

from app.adapters import REGISTRY
from app.adapters.base import FetchRequest
from app.config import settings
from app.db.engine import session_scope
from app.db.models import Tenant
from app.db.repositories import (
    ArticleRepository,
    PipelineRunRepository,
    SourceRepository,
)
from app.pipeline.dedup import (
    hamming,
    is_better_canonical,
    is_novel,
    novelty_boundary,
    to_unsigned,
)
from app.pipeline.extract import extract_article as _extract_article_stage
from app.pipeline.generation import generate_draft_run as _generate_draft_stage
from app.pipeline.scoring import score_article_run as _score_article_stage
from app.worker.celery_app import celery_app
from app.worker.schedule import local_run_date_if_due


def _uuid(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


# ─────────────────────────────────────────── Guards (fail-open, best-effort)


def _robots_ok(url: str) -> bool:
    if not settings.ingestion_guards_enabled:
        return True
    try:
        from app.worker.robots import RobotsPolicy

        return RobotsPolicy().allowed(url)
    except Exception:
        return True


def _throttle(host: str, rpm: int) -> None:
    if not settings.ingestion_guards_enabled or not host:
        return
    try:
        from app.worker.throttle import RateLimiter

        RateLimiter().wait(host, rpm)
    except Exception:
        return


# ─────────────────────────────────────────── Стадии (sync ядро)


def ingest_source_run(
    source_id, run_id, mode: str = "incremental", since: datetime | None = None
) -> dict:
    """Идемпотентная единица: fetch -> normalize -> novelty -> upsert -> provenance -> advance."""
    source_uuid = _uuid(source_id)
    run_uuid = _uuid(run_id)
    with session_scope() as session:
        source = SourceRepository.get(session, source_uuid)
        if source is None or not source.enabled:
            return _ingest_result(source_id, status="skipped")
        if source.type not in REGISTRY:
            SourceRepository.set_health(
                session,
                source.id,
                last_status="unsupported_type",
                last_error=source.type,
                last_error_at=datetime.now(UTC),
            )
            return _ingest_result(source_id, status="unsupported_type")

        tenant = session.get(Tenant, source.tenant_id)
        tenant_tz = tenant.timezone if tenant is not None else "UTC"
        adapter = REGISTRY[source.type]
        config = source.config or {}
        novelty_days = int(config.get("novelty_days", 0) or 0)
        source_dict = {
            "id": str(source.id),
            "tenant_id": str(source.tenant_id),
            "type": source.type,
            "url": source.url,
            "config": config,
            "priority": source.priority,
        }

        if adapter.capabilities.respects_robots and not _robots_ok(source.url):
            SourceRepository.set_health(
                session,
                source.id,
                last_status="robots_disallowed",
                last_error="robots",
                last_error_at=datetime.now(UTC),
            )
            return _ingest_result(source_id, status="robots_disallowed")
        _throttle(urlsplit(source.url).netloc, adapter.capabilities.default_rate_limit_rpm)

        state = source.state or {}
        new_ids: list[str] = []
        fetched = 0
        new = 0
        skipped = 0
        warnings: list[str] = []
        pages = 0
        max_pages = int(config.get("max_pages", 1) or 1) if mode == "backfill" else 1

        while True:
            request = FetchRequest(source=source_dict, state=state, mode=mode, since=since)
            result = adapter.fetch(request)
            fetched += result.stats.fetched
            warnings.extend(result.warnings)
            state = result.state
            for raw in result.items:
                doc = adapter.normalize(source_dict, raw)
                if not is_novel(
                    doc.published_at,
                    tenant_tz,
                    mode=mode,
                    since=since,
                    novelty_days=novelty_days,
                ):
                    skipped += 1
                    continue
                article_id, inserted = ArticleRepository.upsert_document(
                    session, doc, pipeline_run_id=run_uuid
                )
                if inserted:
                    new += 1
                    new_ids.append(str(article_id))
                    ArticleRepository.upsert_article_source(
                        session,
                        tenant_id=source.tenant_id,
                        article_id=article_id,
                        source_id=source.id,
                        external_id=doc.external_id,
                        priority_at_seen=source.priority,
                    )
                else:
                    existing = ArticleRepository.find_id_by_canonical(
                        session, source.tenant_id, doc.canonical_url
                    )
                    if existing is not None:
                        ArticleRepository.upsert_article_source(
                            session,
                            tenant_id=source.tenant_id,
                            article_id=existing,
                            source_id=source.id,
                            external_id=doc.external_id,
                            priority_at_seen=source.priority,
                        )
            pages += 1
            if not result.has_more or pages >= max_pages:
                break

        SourceRepository.advance_state(
            session, source.id, new_state=state, last_run_at=datetime.now(UTC)
        )
        return _ingest_result(
            source_id,
            new_ids=new_ids,
            fetched=fetched,
            new=new,
            skipped=skipped,
            warnings=warnings,
            status="ok",
        )


def _ingest_result(
    source_id, *, new_ids=None, fetched=0, new=0, skipped=0, warnings=None, status="ok"
) -> dict:
    return {
        "source_id": str(source_id),
        "new_ids": new_ids or [],
        "fetched": fetched,
        "new": new,
        "skipped": skipped,
        "warnings": warnings or [],
        "status": status,
    }


def extract_article_run(article_id, run_id) -> dict:
    with session_scope() as session:
        return _extract_article_stage(session, _uuid(article_id), pipeline_run_id=_uuid(run_id))


def score_article_run(article_id, run_id) -> dict:
    with session_scope() as session:
        return _score_article_stage(session, _uuid(article_id), _uuid(run_id))


def dedup_and_score_run(tenant_id, run_id, *, fetch_stats: dict | None = None) -> dict:
    """Sync-ядро терминала: дедуп -> скоринг выживших -> финализация (барьер по построению)."""
    dedup_articles(tenant_id, run_id)
    score_run(tenant_id, run_id)
    return finalize_run(tenant_id, run_id, fetch_stats=fetch_stats)


def dedup_articles(tenant_id, run_id) -> None:
    """Дедуп по финальному телу (content-hash exact + simhash near-dup) после extract-барьера."""
    tenant_uuid = _uuid(tenant_id)
    run_uuid = _uuid(run_id)
    threshold = settings.near_dup_hamming_threshold
    with session_scope() as session:
        tenant = session.get(Tenant, tenant_uuid)
        tenant_tz = tenant.timezone if tenant is not None else "UTC"
        window_start = novelty_boundary(tenant_tz, novelty_days=1)
        priority = SourceRepository.priority_map(session, tenant_uuid)
        subjects = ArticleRepository.run_articles(session, run_uuid)
        demoted: set = set()

        for subject in subjects:
            if subject.id in demoted:
                continue
            _dedup_exact(session, subject, priority, demoted)
            if subject.id in demoted:
                continue
            _dedup_near(session, subject, priority, demoted, window_start, threshold, tenant_uuid)


def score_run(tenant_id, run_id) -> None:
    """Оценить выживших после дедупа (status='extracted'). Best-effort, каждая статья независимо."""
    run_uuid = _uuid(run_id)
    with session_scope() as session:
        article_ids = [
            str(article.id)
            for article in ArticleRepository.run_articles(
                session, run_uuid, statuses=("extracted",)
            )
        ]
    for article_id in article_ids:
        try:
            score_article_run(article_id, run_id)
        except Exception:
            continue


def finalize_run(tenant_id, run_id, *, fetch_stats: dict | None = None) -> dict:
    """Счётчики прогона + финализация статуса леджера."""
    run_uuid = _uuid(run_id)
    fetch_stats = fetch_stats or {}
    with session_scope() as session:
        counters = ArticleRepository.run_counters(session, run_uuid)
        if "fetched" in fetch_stats:
            counters["fetched"] = fetch_stats["fetched"]
        failed_sources = int(fetch_stats.get("failed_sources", 0))
        status = "partial" if failed_sources else "success"
        stats = {
            "skipped": int(fetch_stats.get("skipped", 0)),
            "failed_sources": failed_sources,
            "warnings": fetch_stats.get("warnings", []),
        }
        PipelineRunRepository.finalize(
            session, run_uuid, counters=counters, status=status, stats=stats
        )
        return {"run_id": str(run_id), "counters": counters, "status": status}


def _priority_of(priority_map: dict, article) -> int:
    if article.source_id is None:
        return 0
    return priority_map.get(article.source_id, 0)


def _pick_canonical(priority: dict, cluster: list):
    """Единственный канон кластера: higher priority, при равенстве — раньше опубликован."""
    winner = cluster[0]
    for article in cluster[1:]:
        if is_better_canonical(
            _priority_of(priority, article),
            article.published_at,
            _priority_of(priority, winner),
            winner.published_at,
        ):
            winner = article
    return winner


def _collapse_cluster(session, priority, demoted: set, cluster: list, method: str) -> None:
    """Схлопнуть кластер к одному канону: все проигравшие -> winner напрямую (без цепочек)."""
    if len(cluster) < 2:
        return
    winner = _pick_canonical(priority, cluster)
    winner_fingerprint = to_unsigned(winner.simhash) if winner.simhash is not None else None
    for article in cluster:
        if article.id == winner.id or article.id in demoted:
            continue
        distance = 0
        if method == "simhash" and winner_fingerprint is not None and article.simhash is not None:
            distance = hamming(winner_fingerprint, to_unsigned(article.simhash))
        if ArticleRepository.mark_duplicate(
            session, article.id, duplicate_of=winner.id, method=method, distance=distance
        ):
            demoted.add(article.id)


def _dedup_exact(session, subject, priority, demoted: set) -> None:
    matches = ArticleRepository.find_by_content_hash(
        session, subject.tenant_id, subject.content_hash, exclude_id=subject.id
    )
    cluster = [subject] + [match for match in matches if match.id not in demoted]
    _collapse_cluster(session, priority, demoted, cluster, "content_hash")


def _dedup_near(session, subject, priority, demoted, window_start, threshold, tenant_uuid) -> None:
    if subject.simhash is None:
        return
    subject_fingerprint = to_unsigned(subject.simhash)
    cluster = [subject]
    for candidate in ArticleRepository.window_candidates(session, tenant_uuid, since=window_start):
        if candidate.id == subject.id or candidate.id in demoted or candidate.simhash is None:
            continue
        if hamming(subject_fingerprint, to_unsigned(candidate.simhash)) <= threshold:
            cluster.append(candidate)
    _collapse_cluster(session, priority, demoted, cluster, "simhash")


def run_tenant_pipeline_sync(
    tenant_id, run_id, mode: str = "incremental", since: datetime | None = None
) -> dict:
    """Синхронный прогон (барьер по построению): ingest источников -> extract новых -> dedup."""
    with session_scope() as session:
        sources = SourceRepository.get_due_sources(session, _uuid(tenant_id), now=datetime.now(UTC))
        source_ids = [str(s.id) for s in sources]

    results = []
    for source_id in source_ids:
        try:
            results.append(ingest_source_run(source_id, run_id, mode, since))
        except Exception as exc:
            results.append(_ingest_result(source_id, status="failed", warnings=[str(exc)]))

    new_ids: list[str] = []
    fetched = 0
    skipped = 0
    failed_sources = 0
    warnings: list[str] = []
    for result in results:
        new_ids.extend(result["new_ids"])
        fetched += result["fetched"]
        skipped += result["skipped"]
        warnings.extend(result["warnings"])
        if result["status"] not in ("ok", "skipped"):
            failed_sources += 1

    for article_id in new_ids:
        try:
            extract_article_run(article_id, run_id)
        except Exception:
            continue

    return dedup_and_score_run(
        tenant_id,
        run_id,
        fetch_stats={
            "fetched": fetched,
            "skipped": skipped,
            "failed_sources": failed_sources,
            "warnings": warnings,
        },
    )


# ─────────────────────────────────────────── Генерация черновиков (on-demand, отдельный поток)


def _scored_candidates(tenant_id, article_ids=None) -> list[str]:
    """id прошедших отбор статей тенанта (status='scored') — кандидаты на черновик."""
    tenant_uuid = _uuid(tenant_id)
    article_uuids = [_uuid(a) for a in article_ids] if article_ids is not None else None
    with session_scope() as session:
        return [
            str(article.id)
            for article in ArticleRepository.scored_articles(
                session, tenant_uuid, article_ids=article_uuids
            )
        ]


def _finalize_generation(results: list[dict]) -> dict:
    """Обновить счётчик drafted затронутых прогонов + агрегат."""
    run_ids = {
        result["run_id"]
        for result in results
        if result.get("status") == "drafted" and result.get("run_id")
    }
    if run_ids:
        with session_scope() as session:
            for run_id in run_ids:
                PipelineRunRepository.refresh_drafted(session, _uuid(run_id))
    return {
        "drafted": sum(1 for result in results if result.get("status") == "drafted"),
        "skipped": sum(1 for result in results if result.get("status") == "skipped"),
        "failed": sum(1 for result in results if result.get("status") == "failed"),
    }


def run_tenant_generation_sync(tenant_id, article_ids=None) -> dict:
    """Синхронная генерация черновиков по scored-хвосту тенанта (для тестов и ручного прогона)."""
    results: list[dict] = []
    for article_id in _scored_candidates(tenant_id, article_ids):
        try:
            results.append(_generate_draft_stage(article_id))
        except Exception as exc:
            results.append({"article_id": article_id, "status": "failed", "error": str(exc)})
    return _finalize_generation(results)


# ─────────────────────────────────────────── Celery-задачи (продакшен, chord-барьер)


@celery_app.task(name="dispatch_due_tenants")
def dispatch_due_tenants() -> list:
    """Beat-heartbeat: для каждого тенанта в его локальный час — атомарный claim прогона.

    Плюс catch-up: перезапуск прогонов, зависших в running (потерян enqueue при недоступности
    брокера или крэш воркера между claim и стартом). Задачи идемпотентны, повтор безопасен.
    """
    now = datetime.now(UTC)
    dispatched: list[tuple[str, str]] = []
    stale: list[tuple[str, str, str]] = []
    cutoff = now - timedelta(minutes=settings.pipeline_run_stale_minutes)
    with session_scope() as session:
        for tenant in session.execute(select(Tenant)).scalars():
            run_date = local_run_date_if_due(tenant.timezone, tenant.pipeline_hour_local, now)
            if run_date is None:
                continue
            run_id = PipelineRunRepository.claim_run(
                session, tenant_id=tenant.id, run_date=run_date, mode="incremental"
            )
            if run_id is not None:
                dispatched.append((str(tenant.id), str(run_id)))
        for run in PipelineRunRepository.stale_running(session, before=cutoff):
            stale.append((str(run.tenant_id), str(run.id), run.mode))
    for tenant_id, run_id in dispatched:
        run_tenant_pipeline.delay(tenant_id, run_id, "incremental", None)
    for tenant_id, run_id, mode in stale:
        run_tenant_pipeline.delay(tenant_id, run_id, mode, None)
    return dispatched


@celery_app.task(name="run_tenant_pipeline")
def run_tenant_pipeline(tenant_id, run_id, mode="incremental", since=None):
    with session_scope() as session:
        sources = SourceRepository.get_due_sources(session, _uuid(tenant_id), now=datetime.now(UTC))
        source_ids = [str(s.id) for s in sources]
    if not source_ids:
        return dedup_and_score.delay(
            [], tenant_id, run_id, {"fetched": 0, "skipped": 0, "failed_sources": 0}
        )
    from celery import chord, group

    header = group(ingest_source.s(sid, run_id, mode, since) for sid in source_ids)
    return chord(header)(finalize_fetch.s(tenant_id, run_id))


@celery_app.task(name="ingest_source", bind=True, max_retries=5)
def ingest_source(self, source_id, run_id, mode="incremental", since=None):
    """Header-задача chord: НИКОГДА не завершается в FAILURE, иначе Celery не запустит body.

    Только transient-ошибки ретраятся с backoff; всё остальное возвращает failed-sentinel,
    чтобы finalize_fetch/dedup_and_score всё равно отработали (partial-run инвариант).
    """
    from app.worker.errors import TransientFetchError

    try:
        return ingest_source_run(source_id, run_id, mode, since)
    except TransientFetchError as exc:
        if self.request.retries >= self.max_retries:
            return _ingest_result(source_id, status="failed", warnings=[str(exc)])
        raise self.retry(exc=exc, countdown=min(600, 10 * (2**self.request.retries))) from exc
    except Exception as exc:
        return _ingest_result(source_id, status="failed", warnings=[str(exc)])


@celery_app.task(name="finalize_fetch")
def finalize_fetch(results, tenant_id, run_id):
    new_ids: list[str] = []
    fetched = 0
    skipped = 0
    failed_sources = 0
    warnings: list[str] = []
    for result in results or []:
        if not result:
            failed_sources += 1
            continue
        new_ids.extend(result.get("new_ids", []))
        fetched += result.get("fetched", 0)
        skipped += result.get("skipped", 0)
        warnings.extend(result.get("warnings", []))
        if result.get("status") not in ("ok", "skipped"):
            failed_sources += 1

    fetch_stats = {
        "fetched": fetched,
        "skipped": skipped,
        "failed_sources": failed_sources,
        "warnings": warnings,
    }
    if not new_ids:
        return dedup_and_score.delay([], tenant_id, run_id, fetch_stats)

    from celery import chord, group

    header = group(extract_article.s(article_id, run_id) for article_id in new_ids)
    return chord(header)(dedup_and_score.s(tenant_id, run_id, fetch_stats))


@celery_app.task(name="extract_article", bind=True, max_retries=3)
def extract_article(self, article_id, run_id):
    """Header-задача extract-chord: не падает в FAILURE, иначе dedup_and_score не выстрелит."""
    from app.worker.errors import TransientFetchError

    try:
        return extract_article_run(article_id, run_id)
    except TransientFetchError as exc:
        if self.request.retries >= self.max_retries:
            return {"article_id": str(article_id), "status": "failed", "error": str(exc)}
        raise self.retry(exc=exc, countdown=min(600, 10 * (2**self.request.retries))) from exc
    except Exception as exc:
        return {"article_id": str(article_id), "status": "failed", "error": str(exc)}


@celery_app.task(name="dedup_and_score")
def dedup_and_score(results, tenant_id, run_id, fetch_stats=None):
    """Терминал после extract-барьера: дедуп -> chord(скоринг выживших) -> финализация."""
    dedup_articles(tenant_id, run_id)
    run_uuid = _uuid(run_id)
    with session_scope() as session:
        article_ids = [
            str(article.id)
            for article in ArticleRepository.run_articles(
                session, run_uuid, statuses=("extracted",)
            )
        ]
    if not article_ids:
        return finalize_run_task.delay([], tenant_id, run_id, fetch_stats)

    from celery import chord, group

    header = group(score_article.s(article_id, run_id) for article_id in article_ids)
    return chord(header)(finalize_run_task.s(tenant_id, run_id, fetch_stats))


@celery_app.task(name="score_article", bind=True, max_retries=3)
def score_article(self, article_id, run_id):
    """Header-задача score-chord: не падает в FAILURE, иначе finalize_run не выстрелит.

    Transient-ошибки LLM (rate limit / timeout — free-tier бьёт per-minute квоту) ретраятся
    с backoff; остальное возвращает failed-sentinel (partial-run инвариант).
    """
    import litellm

    transient = (
        litellm.RateLimitError,
        litellm.Timeout,
        litellm.APIConnectionError,
        litellm.InternalServerError,
    )
    try:
        return score_article_run(article_id, run_id)
    except transient as exc:
        if self.request.retries >= self.max_retries:
            return {"article_id": str(article_id), "status": "failed", "error": str(exc)}
        raise self.retry(exc=exc, countdown=min(600, 10 * (2**self.request.retries))) from exc
    except Exception as exc:
        return {"article_id": str(article_id), "status": "failed", "error": str(exc)}


@celery_app.task(name="finalize_run")
def finalize_run_task(results, tenant_id, run_id, fetch_stats=None):
    return finalize_run(tenant_id, run_id, fetch_stats=fetch_stats or {})


# ─────────────────────────────────────────── Генерация черновиков (on-demand chord)


@celery_app.task(name="run_tenant_generation")
def run_tenant_generation(tenant_id, article_ids=None):
    """Вход on-demand генерации: fan-out черновиков по scored-хвосту -> обновление счётчика."""
    candidates = _scored_candidates(tenant_id, article_ids)
    if not candidates:
        return {"tenant_id": str(tenant_id), "candidates": 0, "drafted": 0}
    from celery import chord, group

    header = group(generate_article.s(article_id) for article_id in candidates)
    return chord(header)(finalize_generation.s(tenant_id))


@celery_app.task(name="generate_article", bind=True, max_retries=3)
def generate_article(self, article_id):
    """Header-задача generate-chord: не падает в FAILURE, иначе finalize_generation не выстрелит.

    Transient-ошибки LLM (rate limit / timeout сильной модели) ретраятся с backoff;
    остальное возвращает failed-sentinel (инвариант достижимости finalize).
    """
    import litellm

    transient = (
        litellm.RateLimitError,
        litellm.Timeout,
        litellm.APIConnectionError,
        litellm.InternalServerError,
    )
    try:
        return _generate_draft_stage(article_id)
    except transient as exc:
        if self.request.retries >= self.max_retries:
            return {"article_id": str(article_id), "status": "failed", "error": str(exc)}
        raise self.retry(exc=exc, countdown=min(600, 10 * (2**self.request.retries))) from exc
    except Exception as exc:
        return {"article_id": str(article_id), "status": "failed", "error": str(exc)}


@celery_app.task(name="finalize_generation")
def finalize_generation(results, tenant_id):
    return _finalize_generation(results or [])
