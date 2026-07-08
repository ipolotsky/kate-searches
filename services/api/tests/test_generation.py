"""Юнит-генерация: build_messages, форматтер few-shot и решающая логика generate_draft_run.

Без сети/БД: LLM и репозитории замоканы, сессия — фейковый context-manager.
"""

import uuid
from types import SimpleNamespace

import pytest

from app.models.drafts import DraftPost, FAQItem
from app.models.scoring import CriterionScore, RelevanceScore
from app.pipeline import generation


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
        decision_summary="берём: сильный ресейл-сигнал",
    )


def _draft() -> DraftPost:
    return DraftPost(
        language="en",
        title="Archive drop guide",
        suggested_titles=["A", "B", "C"],
        meta_description="meta",
        body_markdown="## Answer-first\nbody",
        faq=[FAQItem(question="q?", answer="a")],
        keywords=["archive", "resale"],
        entities=["Nike"],
        brand_tie_in="ресейл-угол бренда",
        seo_instructions="Article + FAQPage",
        json_ld={"@type": "Article"},
    )


class _FakeSession:
    def __init__(self, tenant: object) -> None:
        self._tenant = tenant

    def get(self, model: object, ident: object) -> object:
        return self._tenant

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def test_build_messages_includes_company_voice_and_language() -> None:
    doc = SimpleNamespace(
        title="Nike archive", body="body", url="https://n.test/x", published_at=None
    )
    profile = {
        "company_name": "LOOTON",
        "company_description": "ресейл премиум-одежды",
        "audience_description": "коллекционеры и сникерхеды",
        "voice_config": {"tone": "expert"},
        "voice_examples": [],
        "unique_angle_hint": "ресейл/архив",
    }
    messages = generation.build_messages(doc, _relevance(), profile, "ru")
    system = messages[0]["content"]
    assert "LOOTON" in system
    assert "ресейл премиум-одежды" in system  # company_description
    assert "коллекционеры и сникерхеды" in system  # audience_description
    assert "ресейл/архив" in system
    assert "Голос и тон: expert" in system  # tone читаемым текстом, не repr словаря
    assert "{'tone'" not in system  # voice_config не утекает как Python-dict
    assert "Язык черновика: ru" in system
    user = messages[1]["content"]
    assert "неизвестна" in user  # published_at None -> guard, без краша
    assert "архивный дроп" in user  # trend_explanation
    assert "берём: сильный ресейл-сигнал" in user  # decision_summary


def test_voice_config_angle_not_duplicated() -> None:
    doc = SimpleNamespace(title="t", body="b", url="https://n.test/x", published_at=None)
    profile = {
        "company_name": "LOOTON",
        "voice_config": {"tone": "дружелюбно", "unique_angle_hint": "ресейл-угол"},
        "voice_examples": [],
        "unique_angle_hint": "ресейл-угол",
    }
    system = generation.build_messages(doc, _relevance(), profile, "ru")[0]["content"]
    assert "дружелюбно" in system
    # unique_angle_hint не задвоился — только в {unique_angle}
    assert system.count("ресейл-угол") == 1


def test_format_examples_caps_three_and_reads_dicts() -> None:
    examples = [
        {"post_text": "первый", "why": "хорош"},
        {"text": "второй"},
        "третий",
        {"post_text": "четвёртый"},
    ]
    formatted = generation._format_examples(examples)
    assert "первый" in formatted
    assert "хорош" in formatted
    assert "второй" in formatted
    assert "третий" in formatted
    assert "четвёртый" not in formatted  # кап 3


def test_format_examples_empty_is_neutral() -> None:
    assert "Примеров пока нет" in generation._format_examples([])


def test_format_examples_shows_source_url_infopovod() -> None:
    examples = [
        {"post_text": "текст поста", "source_url": "https://src.test/a", "why": "хорош"},
        {"post_text": "без источника"},
    ]
    formatted = generation._format_examples(examples)
    assert "Инфоповод: https://src.test/a" in formatted  # source_url в промпте
    assert "Пост: текст поста" in formatted
    assert "Пост: без источника" in formatted
    assert formatted.count("Инфоповод:") == 1  # у второго примера url пустой -> строки нет


def _article(status: str = "scored") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        status=status,
        relevance=_relevance().model_dump(),
        title="Nike archive",
        url="https://n.test/x",
        published_at=None,
        body="body",
        language="en",
        last_pipeline_run_id=uuid.uuid4(),
    )


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    *,
    article,
    profile_row,
    captured: dict,
    called: dict,
    claimed: bool = True,
    advanced: bool = True,
) -> object:
    tenant = SimpleNamespace(name="LOOTON", default_locale="en")
    monkeypatch.setattr(generation.ArticleRepository, "get", staticmethod(lambda s, aid: article))
    monkeypatch.setattr(
        generation.BrandProfileRepository,
        "get_by_tenant",
        staticmethod(lambda s, tid: profile_row),
    )
    monkeypatch.setattr(
        generation.ArticleRepository, "claim_for_draft", staticmethod(lambda s, aid: claimed)
    )
    monkeypatch.setattr(
        generation.ArticleRepository, "advance_drafted", staticmethod(lambda s, aid: advanced)
    )

    def fake_release(s, aid) -> bool:
        called["released"] = True
        return True

    monkeypatch.setattr(
        generation.ArticleRepository, "release_draft_claim", staticmethod(fake_release)
    )

    def fake_create(session, **kwargs) -> uuid.UUID:
        captured.update(kwargs)
        return uuid.uuid4()

    monkeypatch.setattr(generation.PostRepository, "create_from_draft", staticmethod(fake_create))

    def fake_generate(*a, **k):
        called["llm"] = True
        return (_draft(), 0.0123)

    monkeypatch.setattr(generation, "generate_draft", fake_generate)
    return lambda: _FakeSession(tenant)


def test_generate_draft_run_happy_path_persists_post(monkeypatch: pytest.MonkeyPatch) -> None:
    article = _article()
    profile_row = SimpleNamespace(
        company_description="c",
        audience_description="a",
        voice_config={},
        voice_examples=[],
        locales=["en"],
    )
    captured: dict = {}
    called: dict = {}
    factory = _wire(
        monkeypatch, article=article, profile_row=profile_row, captured=captured, called=called
    )

    result = generation.generate_draft_run(article.id, session_factory=factory)

    assert result["status"] == "drafted"
    assert called["llm"] is True
    assert captured["ai_cost_usd"] == 0.0123
    assert captured["ai_model"] == generation.settings.llm_model_draft
    assert captured["language"] == "en"
    assert isinstance(captured["draft"], DraftPost)


def test_generate_draft_run_concurrent_loser_skips_before_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    article = _article()
    profile_row = SimpleNamespace(
        company_description="c",
        audience_description="a",
        voice_config={},
        voice_examples=[],
        locales=["en"],
    )
    captured: dict = {}
    called: dict = {}
    factory = _wire(
        monkeypatch,
        article=article,
        profile_row=profile_row,
        captured=captured,
        called=called,
        claimed=False,
    )

    result = generation.generate_draft_run(article.id, session_factory=factory)

    assert result["status"] == "skipped"
    assert result["reason"] == "already_claimed"
    assert "llm" not in called  # сильная модель НЕ вызвана — нет double-spend
    assert captured == {}  # пост не создан


def test_generate_draft_run_releases_claim_on_llm_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    article = _article()
    profile_row = SimpleNamespace(
        company_description="c",
        audience_description="a",
        voice_config={},
        voice_examples=[],
        locales=["en"],
    )
    captured: dict = {}
    called: dict = {}
    factory = _wire(
        monkeypatch, article=article, profile_row=profile_row, captured=captured, called=called
    )
    monkeypatch.setattr(
        generation, "generate_draft", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    with pytest.raises(RuntimeError):
        generation.generate_draft_run(article.id, session_factory=factory)

    assert called.get("released") is True  # claim откачен drafting -> scored
    assert captured == {}


def test_generate_draft_run_skips_non_scored(monkeypatch: pytest.MonkeyPatch) -> None:
    article = _article(status="drafted")
    monkeypatch.setattr(generation.ArticleRepository, "get", staticmethod(lambda s, aid: article))
    factory = lambda: _FakeSession(SimpleNamespace(name="x", default_locale="en"))  # noqa: E731
    result = generation.generate_draft_run(article.id, session_factory=factory)
    assert result["status"] == "skipped"


def test_generate_draft_run_skips_without_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    article = _article()
    monkeypatch.setattr(generation.ArticleRepository, "get", staticmethod(lambda s, aid: article))
    monkeypatch.setattr(
        generation.BrandProfileRepository, "get_by_tenant", staticmethod(lambda s, tid: None)
    )
    factory = lambda: _FakeSession(SimpleNamespace(name="x", default_locale="en"))  # noqa: E731
    result = generation.generate_draft_run(article.id, session_factory=factory)
    assert result["status"] == "skipped"
    assert result["reason"] == "no_brand_profile"
