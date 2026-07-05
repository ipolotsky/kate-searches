"""Celery-приложение: broker + result backend на redis.

Result backend включён с M1 — нужен для chord-барьеров дедупа и скоринга и для
chaining M3. Очереди default/fetch/extract/score с роутингом по имени задачи.
"""

from celery import Celery

from app.config import settings

DISPATCH_INTERVAL_SECONDS = 15 * 60


def create_celery() -> Celery:
    app = Celery(
        "katesearches",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["app.worker.tasks"],
    )
    app.conf.update(
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
        result_expires=24 * 60 * 60,
        broker_transport_options={"visibility_timeout": 3600},
        task_default_queue="default",
        task_routes={
            "ingest_source": {"queue": "fetch"},
            "extract_article": {"queue": "extract"},
            "score_article": {"queue": "score"},
            "run_tenant_pipeline": {"queue": "default"},
            "finalize_fetch": {"queue": "default"},
            "dedup_and_score": {"queue": "default"},
            "finalize_run": {"queue": "default"},
            "dispatch_due_tenants": {"queue": "default"},
        },
        beat_schedule={
            "dispatch-due-tenants": {
                "task": "dispatch_due_tenants",
                "schedule": float(DISPATCH_INTERVAL_SECONDS),
            }
        },
    )
    return app


celery_app = create_celery()
