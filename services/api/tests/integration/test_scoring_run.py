"""E2E скоринг: extracted -> scored|filtered_out через run_tenant_pipeline_sync.

Прогон на реальном Supabase, LLM-вызов замокан (scoring.score_article), гейты выключены.
Проверяет переход статуса, relevance/relevance_score и счётчики scored/filtered_out прогона.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from app.config import settings
from app.db.engine import session_scope
from app.db.models import Article, BrandProfile, PipelineRun, Source, Tenant
from app.db.repositories import PipelineRunRepository
from app.models.scoring import CriterionScore, RelevanceScore
from app.worker.tasks import run_tenant_pipeline_sync

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _allow_test_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    # SSRF-guard (assert_public_url) в проде всегда включён и НЕ гейтится ingestion_guards_enabled.
    # .test-хосты фикстур не резолвятся (dns_error), а фид мокается и реальной сети нет —
    # поэтому здесь guard отключаем, как в test_health.
    monkeypatch.setattr("app.adapters.rss.assert_public_url", lambda url: None)


_BODY_HOT = "Hot fresh archive drop unique collector story. " * 30
_BODY_COLD = "Cold unrelated weather report filler copy. " * 30


class _FakeParsed:
    def __init__(self, entries: list) -> None:
        self.entries = entries
        self.etag = None
        self.bozo = 0


def _entry(guid: str, link: str, body: str, when: datetime) -> dict:
    return {
        "id": guid,
        "link": link,
        "title": guid,
        "summary": "summary",
        "content": [{"value": body}],
        "published_parsed": when.timetuple(),
    }


def _relevance(*, overall: int, passes: bool) -> RelevanceScore:
    criterion = CriterionScore(reasoning="ok", score="high")
    return RelevanceScore(
        news_potential=criterion,
        resale_potential=criterion,
        commercial_potential=criterion,
        trend_potential=criterion,
        trend_explanation="trend",
        seo_potential=criterion,
        aeo_potential=criterion,
        content_potential=criterion,
        content_cluster_potential=criterion,
        knowledge_gap_potential=criterion,
        unique_angle=criterion,
        overall_score=overall,
        publication_priority="HOT" if passes else "DROP",
        passes_threshold=passes,
        decision_summary="s",
    )


@pytest.fixture
def tenant_setup() -> Iterator[uuid.UUID]:
    tenant_id = uuid.uuid4()
    with session_scope() as session:
        session.add(Tenant(id=tenant_id, name="LOOTON", timezone="UTC", pipeline_hour_local=6))
        session.flush()
        session.add(
            BrandProfile(
                tenant_id=tenant_id,
                company_description="resale маркетплейс",
                audience_description="коллекционеры",
                filter_criteria="берём релизы и архивы, отбрасываем офтоп",
                criteria_weights={"resale_potential": 2.0},
                score_threshold=60,
            )
        )
        session.add(
            Source(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                type="rss",
                url="https://s.test/feed",
                priority=5,
                enabled=True,
            )
        )
    try:
        yield tenant_id
    finally:
        with session_scope() as session:
            session.query(Tenant).filter_by(id=tenant_id).delete()


def _install_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    when = datetime.now(UTC) - timedelta(hours=2)
    entries = [
        _entry("hot", "https://n.test/hot", _BODY_HOT, when),
        _entry("cold", "https://n.test/cold", _BODY_COLD, when),
    ]
    monkeypatch.setattr(
        "app.adapters.rss.feedparser.parse",
        lambda url, etag=None: _FakeParsed(entries),
    )
    monkeypatch.setattr(settings, "ingestion_guards_enabled", False)

    def fake_score(doc, profile, tenant_id, *, pipeline_run_id=None) -> RelevanceScore:
        hot = "hot" in (doc.title or "").lower()
        return _relevance(overall=80 if hot else 30, passes=hot)

    monkeypatch.setattr("app.pipeline.scoring.score_article", fake_score)


def test_scoring_run_splits_scored_and_filtered(
    tenant_setup: uuid.UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant_id = tenant_setup
    _install_feed(monkeypatch)

    with session_scope() as session:
        run_id = PipelineRunRepository.claim_run(
            session, tenant_id=tenant_id, run_date=datetime.now(UTC).date()
        )
    assert run_id is not None

    outcome = run_tenant_pipeline_sync(tenant_id, run_id)
    assert outcome["status"] == "success"

    with session_scope() as session:
        by_url = {
            row.canonical_url: row for row in session.query(Article).filter_by(tenant_id=tenant_id)
        }
        hot = by_url["https://n.test/hot"]
        cold = by_url["https://n.test/cold"]

        assert hot.status == "scored"
        assert hot.relevance_score == 80
        assert hot.relevance is not None
        assert hot.relevance["publication_priority"] == "HOT"

        assert cold.status == "filtered_out"
        assert cold.relevance_score == 30
        assert cold.relevance is not None

        run = session.get(PipelineRun, run_id)
        assert run.scored == 1
        assert run.filtered_out == 1


def test_scoring_run_without_profile_leaves_extracted(
    tenant_setup: uuid.UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant_id = tenant_setup
    _install_feed(monkeypatch)
    with session_scope() as session:
        session.query(BrandProfile).filter_by(tenant_id=tenant_id).delete()

    with session_scope() as session:
        run_id = PipelineRunRepository.claim_run(
            session, tenant_id=tenant_id, run_date=datetime.now(UTC).date()
        )

    outcome = run_tenant_pipeline_sync(tenant_id, run_id)
    assert outcome["status"] == "success"

    with session_scope() as session:
        statuses = {row.status for row in session.query(Article).filter_by(tenant_id=tenant_id)}
        assert statuses == {"extracted"}
        run = session.get(PipelineRun, run_id)
        assert run.scored == 0
        assert run.filtered_out == 0
