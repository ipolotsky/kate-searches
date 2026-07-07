"""E2E acceptance AC-1: свежесть по tz, URL/контент-дедуп, идемпотентность, провенанс.

Прогон на реальном Supabase через run_tenant_pipeline_sync (барьер по построению).
feedparser замокан, robots/throttle-гейты выключены. Два rss-источника с разным priority.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from app.config import settings
from app.db.engine import session_scope
from app.db.models import Article, ArticleSource, PipelineRun, Source, Tenant
from app.db.repositories import PipelineRunRepository
from app.worker.celery_app import celery_app
from app.worker.tasks import finalize_fetch, run_tenant_pipeline_sync

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _allow_test_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    # SSRF-guard (assert_public_url) в проде всегда включён и НЕ гейтится ingestion_guards_enabled.
    # .test-хосты фикстур не резолвятся (dns_error), а фид мокается и реальной сети нет —
    # поэтому здесь guard отключаем, как в test_health.
    monkeypatch.setattr("app.adapters.rss.assert_public_url", lambda url: None)


_LONG_FRESH = "Fresh unique archive drop coverage. " * 30
_DUP_BODY = "Shared wire copy about the same archive reissue story. " * 30
_LONG_SHARED = "A distinct syndicated column carried by two feeds verbatim. " * 30


class _FakeParsed:
    def __init__(self, entries):
        self.entries = entries
        self.etag = None
        self.bozo = 0


def _entry(guid, link, body, when: datetime | None):
    entry = {
        "id": guid,
        "link": link,
        "title": guid,
        "summary": "summary",
        "content": [{"value": body}],
    }
    if when is not None:
        entry["published_parsed"] = when.timetuple()
    return entry


@pytest.fixture
def tenant_setup() -> Iterator[tuple[uuid.UUID, uuid.UUID, uuid.UUID]]:
    tenant_id = uuid.uuid4()
    source_a = uuid.uuid4()
    source_b = uuid.uuid4()
    with session_scope() as session:
        session.add(Tenant(id=tenant_id, name="ac1", timezone="UTC", pipeline_hour_local=6))
        session.flush()
        session.add(
            Source(
                id=source_a,
                tenant_id=tenant_id,
                type="rss",
                url="https://a.test/feed",
                priority=5,
                enabled=True,
            )
        )
        session.add(
            Source(
                id=source_b,
                tenant_id=tenant_id,
                type="rss",
                url="https://b.test/feed",
                priority=3,
                enabled=True,
            )
        )
    try:
        yield tenant_id, source_a, source_b
    finally:
        with session_scope() as session:
            session.query(Tenant).filter_by(id=tenant_id).delete()


def _install_feeds(monkeypatch) -> None:
    now = datetime.now(UTC)
    today = now - timedelta(hours=2)
    old = now - timedelta(days=3)
    feed_a = [
        _entry("fresh", "https://news.test/fresh", _LONG_FRESH, today),
        _entry("dup-a", "https://news.test/dup-a", _DUP_BODY, today),
        _entry("shared", "https://news.test/shared", _LONG_SHARED, today),
        _entry("old", "https://news.test/old", _LONG_FRESH + " old", old),
        _entry("dateless", "https://news.test/dateless", _LONG_FRESH + " dateless", None),
    ]
    feed_b = [
        _entry("dup-b", "https://news.test/dup-b", _DUP_BODY, today),
        _entry("shared", "https://news.test/shared", _LONG_SHARED, today),
    ]
    feeds = {"https://a.test/feed": feed_a, "https://b.test/feed": feed_b}
    monkeypatch.setattr(
        "app.adapters.rss.feedparser.parse",
        lambda url, etag=None: _FakeParsed(feeds.get(url, [])),
    )
    monkeypatch.setattr(settings, "ingestion_guards_enabled", False)


def _articles(session, tenant_id) -> dict[str, Article]:
    rows = session.query(Article).filter_by(tenant_id=tenant_id).all()
    return {row.canonical_url: row for row in rows}


def test_ac1_full_run(tenant_setup, monkeypatch) -> None:
    tenant_id, source_a, source_b = tenant_setup
    _install_feeds(monkeypatch)

    with session_scope() as session:
        run_id = PipelineRunRepository.claim_run(
            session, tenant_id=tenant_id, run_date=datetime.now(UTC).date()
        )
    assert run_id is not None

    outcome = run_tenant_pipeline_sync(tenant_id, run_id)
    assert outcome["status"] == "success"

    with session_scope() as session:
        by_url = _articles(session, tenant_id)

        # старьё и dateless не создаются (AC-1 п.1)
        assert "https://news.test/old" not in by_url
        assert "https://news.test/dateless" not in by_url

        # ровно свежие уникальные + контент-дубль + shared
        assert set(by_url) == {
            "https://news.test/fresh",
            "https://news.test/dup-a",
            "https://news.test/dup-b",
            "https://news.test/shared",
        }

        fresh = by_url["https://news.test/fresh"]
        dup_a = by_url["https://news.test/dup-a"]
        dup_b = by_url["https://news.test/dup-b"]
        shared = by_url["https://news.test/shared"]

        assert fresh.status == "extracted"
        assert shared.status == "extracted"

        # кросс-источниковый контент-дубль схлопнут: priority 5 (A) побеждает 3 (B)
        assert dup_a.status == "extracted"
        assert dup_b.status == "duplicate"
        assert dup_b.duplicate_of == dup_a.id
        assert dup_b.doc_metadata.get("dedup_method") == "content_hash"

        # каноничность не демоучена
        assert dup_a.duplicate_of is None

        # провенанс: shared виден из обоих источников (URL-дубль append, не overwrite)
        shared_sources = session.query(ArticleSource).filter_by(article_id=shared.id).all()
        assert {s.source_id for s in shared_sources} == {source_a, source_b}

        # леджер прогона
        run = session.get(PipelineRun, run_id)
        assert run.status == "success"
        assert run.extracted == 3
        assert run.duplicated == 1


def test_ac1_rerun_is_idempotent(tenant_setup, monkeypatch) -> None:
    tenant_id, _a, _b = tenant_setup
    _install_feeds(monkeypatch)

    with session_scope() as session:
        run1 = PipelineRunRepository.claim_run(
            session, tenant_id=tenant_id, run_date=datetime.now(UTC).date()
        )
    run_tenant_pipeline_sync(tenant_id, run1)

    with session_scope() as session:
        count_after_first = session.query(Article).filter_by(tenant_id=tenant_id).count()

    with session_scope() as session:
        run2 = PipelineRunRepository.claim_run(
            session, tenant_id=tenant_id, run_date=datetime.now(UTC).date() + timedelta(days=1)
        )
    outcome2 = run_tenant_pipeline_sync(tenant_id, run2)

    with session_scope() as session:
        count_after_second = session.query(Article).filter_by(tenant_id=tenant_id).count()
        run2_row = session.get(PipelineRun, run2)

    assert count_after_second == count_after_first
    assert outcome2["status"] == "success"
    assert run2_row.status == "success"
    assert run2_row.new == 0


def _seed_tenant_with_sources(priorities: list[int]) -> tuple[uuid.UUID, list[uuid.UUID]]:
    tenant_id = uuid.uuid4()
    source_ids = [uuid.uuid4() for _ in priorities]
    with session_scope() as session:
        session.add(Tenant(id=tenant_id, name="cluster", timezone="UTC", pipeline_hour_local=6))
        session.flush()
        for source_id, priority in zip(source_ids, priorities, strict=True):
            session.add(
                Source(
                    id=source_id,
                    tenant_id=tenant_id,
                    type="rss",
                    url=f"https://s{source_id.hex[:6]}.test/feed",
                    priority=priority,
                    enabled=True,
                )
            )
    return tenant_id, source_ids


def test_content_cluster_collapses_to_single_canonical(monkeypatch) -> None:
    """Три источника, одинаковый контент -> один канон (priority 5), остальные прямо на него."""
    tenant_id, (src_lo, src_hi, src_mid) = _seed_tenant_with_sources([3, 5, 4])
    monkeypatch.setattr(settings, "ingestion_guards_enabled", False)
    today = datetime.now(UTC) - timedelta(hours=2)
    body = "Identical syndicated cluster copy across three feeds. " * 30
    feeds = {
        f"https://s{src_lo.hex[:6]}.test/feed": [_entry("lo", "https://n.test/lo", body, today)],
        f"https://s{src_hi.hex[:6]}.test/feed": [_entry("hi", "https://n.test/hi", body, today)],
        f"https://s{src_mid.hex[:6]}.test/feed": [_entry("mid", "https://n.test/mid", body, today)],
    }
    monkeypatch.setattr(
        "app.adapters.rss.feedparser.parse",
        lambda url, etag=None: _FakeParsed(feeds.get(url, [])),
    )
    try:
        with session_scope() as session:
            run_id = PipelineRunRepository.claim_run(
                session, tenant_id=tenant_id, run_date=datetime.now(UTC).date()
            )
        run_tenant_pipeline_sync(tenant_id, run_id)

        with session_scope() as session:
            rows = {
                a.canonical_url: a for a in session.query(Article).filter_by(tenant_id=tenant_id)
            }
            hi = rows["https://n.test/hi"]
            lo = rows["https://n.test/lo"]
            mid = rows["https://n.test/mid"]
            # ровно один канон — из источника с priority 5
            assert hi.status == "extracted"
            assert hi.duplicate_of is None
            # оба проигравших указывают ПРЯМО на канон (без цепочек через промежуточный дубль)
            assert lo.status == "duplicate" and lo.duplicate_of == hi.id
            assert mid.status == "duplicate" and mid.duplicate_of == hi.id
    finally:
        with session_scope() as session:
            session.query(Tenant).filter_by(id=tenant_id).delete()


def test_failing_source_does_not_hang_run(monkeypatch) -> None:
    """Один упавший источник не роняет прогон: остальные обрабатываются, run -> partial."""
    tenant_id, (src_ok, src_bad) = _seed_tenant_with_sources([5, 3])
    monkeypatch.setattr(settings, "ingestion_guards_enabled", False)
    today = datetime.now(UTC) - timedelta(hours=2)
    bad_url = f"https://s{src_bad.hex[:6]}.test/feed"
    ok_body = "A perfectly good fresh article body for the healthy source feed. " * 20

    def flaky_parse(url, etag=None):
        if url == bad_url:
            raise RuntimeError("source is down")
        return _FakeParsed([_entry("ok", "https://n.test/ok", ok_body, today)])

    monkeypatch.setattr("app.adapters.rss.feedparser.parse", flaky_parse)
    try:
        with session_scope() as session:
            run_id = PipelineRunRepository.claim_run(
                session, tenant_id=tenant_id, run_date=datetime.now(UTC).date()
            )
        outcome = run_tenant_pipeline_sync(tenant_id, run_id)

        assert outcome["status"] == "partial"
        with session_scope() as session:
            rows = {
                a.canonical_url: a for a in session.query(Article).filter_by(tenant_id=tenant_id)
            }
            assert rows["https://n.test/ok"].status == "extracted"
            run = session.get(PipelineRun, run_id)
            assert run.status == "partial"
            assert run.finished_at is not None
    finally:
        with session_scope() as session:
            session.query(Tenant).filter_by(id=tenant_id).delete()


def test_empty_run_finalizes_via_chord_guard(tenant_setup, monkeypatch) -> None:
    """finalize_fetch с нулём новых зовёт dedup напрямую (chord не зависает)."""
    tenant_id, _a, _b = tenant_setup
    monkeypatch.setattr(settings, "ingestion_guards_enabled", False)
    monkeypatch.setitem(celery_app.conf, "task_always_eager", True)

    with session_scope() as session:
        run_id = PipelineRunRepository.claim_run(
            session, tenant_id=tenant_id, run_date=datetime.now(UTC).date()
        )

    finalize_fetch([], str(tenant_id), str(run_id))

    with session_scope() as session:
        run = session.get(PipelineRun, run_id)
    assert run.status == "success"
    assert run.finished_at is not None
