"""Celery-приложение сконфигурировано под chord-барьер и надёжность."""

from app.worker.celery_app import celery_app


def test_result_backend_enabled_for_chord() -> None:
    assert celery_app.conf.result_backend
    assert celery_app.conf.result_backend.startswith("redis")


def test_reliability_flags() -> None:
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.timezone == "UTC"


def test_task_routing_by_name() -> None:
    routes = celery_app.conf.task_routes
    assert routes["ingest_source"]["queue"] == "fetch"
    assert routes["extract_article"]["queue"] == "extract"


def test_beat_dispatch_scheduled() -> None:
    assert "dispatch-due-tenants" in celery_app.conf.beat_schedule
