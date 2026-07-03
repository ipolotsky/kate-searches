"""LLM-клиент: валидированный ответ + запись стоимости в ai_usage (без сети и БД)."""

import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import instructor
import litellm
import pytest

from app.llm import client as llm_client
from app.models.scoring import CriterionScore, RelevanceScore


def _relevance() -> RelevanceScore:
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
        overall_score=80,
        publication_priority="HOT",
        passes_threshold=True,
        decision_summary="take it",
    )


class _FakeSession:
    def __init__(self, sink: list) -> None:
        self.sink = sink

    def add(self, row: object) -> None:
        self.sink.append(row)

    def flush(self) -> None:
        pass


def test_structured_completion_writes_ai_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    added: list = []

    @contextmanager
    def fake_factory():
        yield _FakeSession(added)

    score = _relevance()
    completion = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1200, completion_tokens=200))

    class _FakeCompletions:
        def create_with_completion(self, **kwargs: object):
            assert kwargs["metadata"]["stage"] == "score"
            assert kwargs["metadata"]["tenant_id"]
            return score, completion

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletions()))
    monkeypatch.setattr(instructor, "from_litellm", lambda _fn: fake_client)
    monkeypatch.setattr(litellm, "completion_cost", lambda **_: 0.00031)

    tenant_id = str(uuid.uuid4())
    result = llm_client.structured_completion(
        model="gemini/gemini-2.0-flash-lite",
        messages=[{"role": "user", "content": "x"}],
        response_model=RelevanceScore,
        tenant_id=tenant_id,
        stage="score",
        session_factory=fake_factory,
    )

    assert isinstance(result, RelevanceScore)
    assert result.overall_score == 80
    assert len(added) == 1
    row = added[0]
    assert str(row.tenant_id) == tenant_id
    assert row.stage == "score"
    assert row.model == "gemini/gemini-2.0-flash-lite"
    assert row.input_tokens == 1200
    assert row.output_tokens == 200
    assert float(row.cost_usd) == pytest.approx(0.00031)
    assert row.request_id
