"""E2E генерация: scored -> drafted + строка posts через run_tenant_generation_sync.

Прогон на реальном Supabase, LLM-вызовы замоканы (score_article + generate_draft), гейты выключены.
Проверяет переход статуса, маппинг DraftPost -> posts, счётчик drafted и идемпотентность.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from app.config import settings
from app.db.engine import session_scope
from app.db.models import Article, BrandProfile, PipelineRun, Post, Source, Tenant
from app.db.repositories import PipelineRunRepository
from app.models.drafts import DraftPost, FAQItem
from app.models.scoring import CriterionScore, RelevanceScore
from app.worker.tasks import run_tenant_generation_sync, run_tenant_pipeline_sync

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _allow_test_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    # SSRF-guard (assert_public_url) в проде всегда включён и НЕ гейтится ingestion_guards_enabled.
    # .test-хосты фикстур не резолвятся (dns_error), а фид мокается и реальной сети нет —
    # поэтому здесь guard отключаем, как в test_health.
    monkeypatch.setattr("app.adapters.rss.assert_public_url", lambda url: None)

_BODY_HOT = "Hot fresh archive drop unique collector story. " * 30
_BODY_COLD = "Cold unrelated weather report filler copy. " * 30
_COST = 0.0123


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


def _relevance() -> RelevanceScore:
    criterion = CriterionScore(reasoning="ok", score="high")
    return RelevanceScore(
        news_potential=criterion,
        resale_potential=criterion,
        commercial_potential=criterion,
        trend_potential=criterion,
        trend_explanation="архивный дроп",
        seo_potential=criterion,
        aeo_potential=criterion,
        content_potential=criterion,
        content_cluster_potential=criterion,
        knowledge_gap_potential=criterion,
        unique_angle=criterion,
        overall_score=80,
        publication_priority="HOT",
        passes_threshold=True,
        decision_summary="берём",
    )


def _draft() -> DraftPost:
    return DraftPost(
        language="en",
        title="Archive drop guide",
        suggested_titles=["First", "Second", "Third"],
        meta_description="meta description",
        body_markdown="## Answer-first\nbody",
        faq=[FAQItem(question="q?", answer="a")],
        keywords=["archive", "resale"],
        entities=["Nike"],
        brand_tie_in="ресейл-угол бренда",
        seo_instructions="Article + FAQPage",
        json_ld={"@type": "Article"},
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
                voice_config={"tone": "expert", "unique_angle_hint": "ресейл/архив"},
                voice_examples=[],
                criteria_weights={"resale_potential": 2.0},
                score_threshold=60,
                locales=["en"],
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


def _install(monkeypatch: pytest.MonkeyPatch) -> None:
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
        score = _relevance()
        if not hot:
            score = score.model_copy(
                update={
                    "overall_score": 30,
                    "publication_priority": "DROP",
                    "passes_threshold": False,
                }
            )
        return score

    monkeypatch.setattr("app.pipeline.scoring.score_article", fake_score)
    monkeypatch.setattr("app.pipeline.generation.generate_draft", lambda *a, **k: (_draft(), _COST))


def _prepare_scored(tenant_id: uuid.UUID) -> uuid.UUID:
    with session_scope() as session:
        run_id = PipelineRunRepository.claim_run(
            session, tenant_id=tenant_id, run_date=datetime.now(UTC).date()
        )
    assert run_id is not None
    outcome = run_tenant_pipeline_sync(tenant_id, run_id)
    assert outcome["status"] == "success"
    return run_id


def test_generation_run_drafts_scored_and_persists_post(
    tenant_setup: uuid.UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant_id = tenant_setup
    _install(monkeypatch)
    run_id = _prepare_scored(tenant_id)

    summary = run_tenant_generation_sync(tenant_id)
    assert summary["drafted"] == 1

    with session_scope() as session:
        by_url = {
            row.canonical_url: row for row in session.query(Article).filter_by(tenant_id=tenant_id)
        }
        hot = by_url["https://n.test/hot"]
        cold = by_url["https://n.test/cold"]
        assert hot.status == "drafted"
        assert cold.status == "filtered_out"

        posts = session.query(Post).filter_by(tenant_id=tenant_id).all()
        assert len(posts) == 1
        post = posts[0]
        assert post.article_id == hot.id
        assert post.title == "Archive drop guide"
        assert post.body_markdown.startswith("## Answer-first")
        assert post.suggested_titles == ["First", "Second", "Third"]
        assert post.faq == [{"question": "q?", "answer": "a"}]
        assert post.seo["brand_tie_in"] == "ресейл-угол бренда"
        assert post.seo["meta_description"] == "meta description"
        assert post.language == "en"
        assert post.ai_model == settings.llm_model_draft
        assert float(post.ai_cost_usd) == _COST

        run = session.get(PipelineRun, run_id)
        assert run.drafted == 1


def test_generation_run_is_idempotent(
    tenant_setup: uuid.UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant_id = tenant_setup
    _install(monkeypatch)
    run_id = _prepare_scored(tenant_id)

    first = run_tenant_generation_sync(tenant_id)
    assert first["drafted"] == 1
    second = run_tenant_generation_sync(tenant_id)
    assert second["drafted"] == 0  # уже drafted -> кандидатов нет

    with session_scope() as session:
        posts = session.query(Post).filter_by(tenant_id=tenant_id).all()
        assert len(posts) == 1  # без дублей
        run = session.get(PipelineRun, run_id)
        assert run.drafted == 1
