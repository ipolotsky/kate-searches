"""Юнит-скоринг: build_messages (веса/критерии) + решающая логика порога (без сети/БД)."""

import uuid
from types import SimpleNamespace

import pytest

from app.models.scoring import CriterionScore, RelevanceScore
from app.pipeline import scoring


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
        publication_priority="HOT",
        passes_threshold=passes,
        decision_summary="s",
    )


def test_build_messages_includes_company_criteria_and_weights() -> None:
    doc = SimpleNamespace(title="T", body="B", url="https://n.test/x", published_at=None)
    profile = {
        "company_name": "LOOTON",
        "company_description": "resale",
        "audience_description": "collectors",
        "filter_criteria": "take releases, drop offtopic",
        "criteria_weights": {"resale_potential": 2.0, "commercial_potential": 1.5},
    }
    messages = scoring.build_messages(doc, profile)
    system = messages[0]["content"]
    assert "LOOTON" in system
    assert "take releases, drop offtopic" in system
    assert "resale_potential" in system
    assert "2.0" in system
    assert "неизвестна" in messages[1]["content"]  # published_at None -> guard


def test_build_messages_empty_weights_is_neutral() -> None:
    doc = SimpleNamespace(title="T", body="B", url="u", published_at=None)
    system = scoring.build_messages(doc, {"criteria_weights": {}})[0]["content"]
    assert "равнозначны" in system


class _FakeSession:
    def get(self, model: object, ident: object) -> object:
        return SimpleNamespace(name="LOOTON")


@pytest.mark.parametrize(
    ("overall", "passes", "threshold", "expected_status", "expected_passed"),
    [
        (80, True, 60, "scored", True),  # оба положительны -> берём
        (50, True, 60, "filtered_out", False),  # score ниже порога -> дроп
        (90, False, 60, "filtered_out", False),  # LLM-вето через passes_threshold -> дроп
    ],
)
def test_gate_decision(
    monkeypatch: pytest.MonkeyPatch,
    overall: int,
    passes: bool,
    threshold: int,
    expected_status: str,
    expected_passed: bool,
) -> None:
    article = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        status="extracted",
        title="t",
        body="b",
        url="u",
        published_at=None,
    )
    profile_row = SimpleNamespace(
        company_description="c",
        audience_description="a",
        filter_criteria="f",
        criteria_weights={},
        score_threshold=threshold,
    )
    captured: dict = {}

    def fake_advance(session, article_id, *, relevance, relevance_score, passed) -> bool:
        captured.update(passed=passed, relevance_score=relevance_score)
        return True

    monkeypatch.setattr(scoring.ArticleRepository, "get", staticmethod(lambda s, aid: article))
    monkeypatch.setattr(
        scoring.BrandProfileRepository, "get_by_tenant", staticmethod(lambda s, tid: profile_row)
    )
    monkeypatch.setattr(scoring.ArticleRepository, "advance_scored", staticmethod(fake_advance))
    monkeypatch.setattr(
        scoring, "score_article", lambda *a, **k: _relevance(overall=overall, passes=passes)
    )

    result = scoring.score_article_run(_FakeSession(), article.id, uuid.uuid4())

    assert result["status"] == expected_status
    assert captured["passed"] is expected_passed
    assert captured["relevance_score"] == overall


def test_score_article_run_skips_non_extracted(monkeypatch: pytest.MonkeyPatch) -> None:
    article = SimpleNamespace(id=uuid.uuid4(), status="scored")
    monkeypatch.setattr(scoring.ArticleRepository, "get", staticmethod(lambda s, aid: article))
    result = scoring.score_article_run(_FakeSession(), article.id, uuid.uuid4())
    assert result["status"] == "skipped"


def test_score_article_run_skips_without_brand_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    article = SimpleNamespace(id=uuid.uuid4(), tenant_id=uuid.uuid4(), status="extracted")
    monkeypatch.setattr(scoring.ArticleRepository, "get", staticmethod(lambda s, aid: article))
    monkeypatch.setattr(
        scoring.BrandProfileRepository, "get_by_tenant", staticmethod(lambda s, tid: None)
    )
    result = scoring.score_article_run(_FakeSession(), article.id, uuid.uuid4())
    assert result["status"] == "skipped"
    assert result["reason"] == "no_brand_profile"
