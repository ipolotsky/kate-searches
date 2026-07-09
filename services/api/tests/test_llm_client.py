"""LLM-клиент: валидированный ответ + запись стоимости в ai_usage (без сети и БД)."""

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import instructor
import litellm
import pytest

from app.llm import client as llm_client
from app.metering import BudgetExceededError, TrialExpiredError
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

    # budget=None => hard-cap не гейтит (reserve пропускается), эти тесты про запись ai_usage.
    def get(self, _model: object, primary_key: object) -> object:
        return SimpleNamespace(id=primary_key, ai_budget_usd_month=None)


class _FakeInstructor:
    """Мини-инструктор: поддерживает .on(hook) и эмулирует completion:response на каждый ответ.

    responses — все ответы модели за вызов (финал + ретраи валидации). Хук фаертся на каждый,
    как в реальном Instructor, а create_with_completion возвращает (result, финальный_ответ).
    """

    def __init__(
        self, result: object, responses: list, *, on_create=None, raise_after=None
    ) -> None:
        self._result = result
        self._responses = responses
        self._on_create = on_create
        self._raise_after = raise_after
        self._hooks: dict = {}
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create_with_completion=self._create)
        )

    def on(self, event: str, handler) -> None:
        self._hooks.setdefault(event, []).append(handler)

    def _create(self, **kwargs: object):
        if self._on_create is not None:
            self._on_create(kwargs)
        for response in self._responses:
            for handler in self._hooks.get("completion:response", []):
                handler(response)
        # Эмуляция исчерпания ретраев валидации: ответы уже оплачены (хук сработал), затем бросок.
        if self._raise_after is not None:
            raise self._raise_after
        return self._result, self._responses[-1]


def test_configure_provider_keys_bridges_settings_to_environ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "explicit-env-key")
    monkeypatch.setattr(llm_client.settings, "gemini_api_key", "gem-from-dotenv")
    monkeypatch.setattr(llm_client.settings, "openai_api_key", "oai-from-dotenv")
    monkeypatch.setattr(llm_client.settings, "anthropic_api_key", "")

    llm_client._configure_provider_keys()

    # пустой в settings -> из .env прокинут в окружение
    assert os.environ["GEMINI_API_KEY"] == "gem-from-dotenv"
    # уже заданный извне ключ не перетирается (setdefault)
    assert os.environ["OPENAI_API_KEY"] == "explicit-env-key"
    # пустой ключ провайдера не создаёт переменную окружения
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_structured_completion_writes_ai_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    added: list = []

    @contextmanager
    def fake_factory():
        yield _FakeSession(added)

    score = _relevance()
    completion = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1200, completion_tokens=200))

    def _assert_meta(kwargs: dict) -> None:
        assert kwargs["metadata"]["stage"] == "score"
        assert kwargs["metadata"]["tenant_id"]

    fake_client = _FakeInstructor(score, [completion], on_create=_assert_meta)
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
    assert row.pipeline_run_id is None


def test_structured_completion_attributes_pipeline_run_id(monkeypatch: pytest.MonkeyPatch) -> None:
    added: list = []

    @contextmanager
    def fake_factory():
        yield _FakeSession(added)

    score = _relevance()
    completion = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))

    fake_client = _FakeInstructor(score, [completion])
    monkeypatch.setattr(instructor, "from_litellm", lambda _fn: fake_client)
    monkeypatch.setattr(litellm, "completion_cost", lambda **_: 0.0)

    run_id = uuid.uuid4()
    llm_client.structured_completion(
        model="gemini/gemini-2.0-flash-lite",
        messages=[{"role": "user", "content": "x"}],
        response_model=RelevanceScore,
        tenant_id=str(uuid.uuid4()),
        stage="score",
        pipeline_run_id=run_id,
        session_factory=fake_factory,
    )

    assert added[0].pipeline_run_id == run_id


def test_structured_completion_blocks_when_budget_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @contextmanager
    def fake_factory():
        yield SimpleNamespace(
            get=lambda _m, pk: SimpleNamespace(
                id=pk, ai_budget_usd_month=Decimal("10"), subscription_status=None
            )
        )

    called = {"llm": False}

    class _FakeCompletions:
        def create_with_completion(self, **_: object):
            called["llm"] = True
            return _relevance(), SimpleNamespace(usage=SimpleNamespace())

    monkeypatch.setattr(
        instructor,
        "from_litellm",
        lambda _fn: SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletions())),
    )
    # Бюджет исчерпан: reserve отказывает. Гейтится только стадия draft (score/ingestion — нет).
    monkeypatch.setattr(llm_client, "reserve_budget", lambda *a, **k: False)

    with pytest.raises(BudgetExceededError):
        llm_client.structured_completion(
            model="openai/gpt-5-mini",
            messages=[{"role": "user", "content": "x"}],
            response_model=RelevanceScore,
            tenant_id=str(uuid.uuid4()),
            stage="draft",
            session_factory=fake_factory,
        )

    assert called["llm"] is False  # заблокировано ДО обращения к модели


def test_structured_completion_survives_usage_write_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Сбой записи ai_usage ПОСЛЕ оплаченного вызова не должен пробрасываться: иначе
    # generate_draft_run поймает исключение, откатит claim и статья перегенерится (двойной
    # расход). Ожидаем (result, cost) без исключения.
    score = _relevance()
    completion = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))

    class _FailingSession:
        def add(self, _row: object) -> None:
            raise RuntimeError("db down")

        def flush(self) -> None:
            pass

        # budget=None => draft не гейтится (reserve возвращает None), тест про запись usage.
        def get(self, _model: object, primary_key: object) -> object:
            return SimpleNamespace(id=primary_key, ai_budget_usd_month=None)

    @contextmanager
    def fake_factory():
        yield _FailingSession()

    monkeypatch.setattr(
        instructor, "from_litellm", lambda _fn: _FakeInstructor(score, [completion])
    )
    monkeypatch.setattr(litellm, "completion_cost", lambda **_: 0.05)

    result, cost = llm_client.structured_completion_with_usage(
        model="openai/gpt-5-mini",
        messages=[{"role": "user", "content": "x"}],
        response_model=RelevanceScore,
        tenant_id=str(uuid.uuid4()),
        stage="draft",
        session_factory=fake_factory,
    )

    assert isinstance(result, RelevanceScore)
    assert cost == pytest.approx(0.05)


def test_structured_completion_sums_retry_attempt_costs(monkeypatch: pytest.MonkeyPatch) -> None:
    # Instructor при провале валидации делает доп. платные вызовы. Учитываем стоимость/токены
    # ВСЕХ попыток (иначе hard-cap недосчитывает расход в 2-4x), а не только финального ответа.
    added: list = []

    @contextmanager
    def fake_factory():
        yield _FakeSession(added)

    score = _relevance()
    responses = [
        SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=100)),
        SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1100, completion_tokens=120)),
        SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1200, completion_tokens=150)),
    ]
    monkeypatch.setattr(instructor, "from_litellm", lambda _fn: _FakeInstructor(score, responses))
    monkeypatch.setattr(litellm, "completion_cost", lambda **_: 0.02)  # 0.02 за каждую попытку

    _result, cost = llm_client.structured_completion_with_usage(
        model="openai/gpt-5-mini",
        messages=[{"role": "user", "content": "x"}],
        response_model=RelevanceScore,
        tenant_id=str(uuid.uuid4()),
        stage="score",
        session_factory=fake_factory,
    )

    assert cost == pytest.approx(0.06)  # 3 попытки * 0.02
    row = added[0]
    assert float(row.cost_usd) == pytest.approx(0.06)
    assert row.input_tokens == 3300  # 1000 + 1100 + 1200
    assert row.output_tokens == 370  # 100 + 120 + 150


def test_records_paid_attempts_when_retries_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ретраи валидации исчерпаны -> Instructor бросает, но попытки уже оплачены. Их стоимость
    # должна попасть в ai_usage (иначе hard-cap не учтёт сожжённые деньги, а полный рефанд обнулит
    # расход). Ранее except делал только рефанд и ничего не записывал.
    added: list = []

    @contextmanager
    def fake_factory():
        yield _FakeSession(added)

    responses = [
        SimpleNamespace(usage=SimpleNamespace(prompt_tokens=900, completion_tokens=80)),
        SimpleNamespace(usage=SimpleNamespace(prompt_tokens=950, completion_tokens=90)),
    ]
    monkeypatch.setattr(
        instructor,
        "from_litellm",
        lambda _fn: _FakeInstructor(
            _relevance(), responses, raise_after=RuntimeError("validation exhausted")
        ),
    )
    monkeypatch.setattr(litellm, "completion_cost", lambda **_: 0.03)

    with pytest.raises(RuntimeError):
        llm_client.structured_completion_with_usage(
            model="openai/gpt-5-mini",
            messages=[{"role": "user", "content": "x"}],
            response_model=RelevanceScore,
            tenant_id=str(uuid.uuid4()),
            stage="draft",
            session_factory=fake_factory,
        )

    assert len(added) == 1  # оплаченные попытки записаны, несмотря на бросок
    assert float(added[0].cost_usd) == pytest.approx(0.06)  # 2 * 0.03
    assert added[0].input_tokens == 1850  # 900 + 950


def _trial_factory(tenant):
    @contextmanager
    def factory():
        yield SimpleNamespace(get=lambda _m, _pk: tenant)

    return factory


def test_reserve_gates_score_on_trial(monkeypatch: pytest.MonkeyPatch) -> None:
    # На триале score тоже идёт через ledger с периодом 'trial' (единый trial-cap на COGS).
    tenant = SimpleNamespace(
        id=uuid.uuid4(),
        ai_budget_usd_month=Decimal("3"),
        subscription_status="trialing",
        trial_ends_at=datetime.now(UTC) + timedelta(days=3),
    )
    captured: dict = {}

    def fake_reserve(session, tenant_id, *, period, estimate, budget) -> bool:
        captured.update(period=period, budget=budget)
        return True

    monkeypatch.setattr(llm_client, "reserve_budget", fake_reserve)
    reservation = llm_client._reserve_budget(
        tenant_id=str(tenant.id), stage="score", session_factory=_trial_factory(tenant)
    )
    assert reservation is not None
    assert reservation[0] == "trial"
    assert captured["period"] == "trial"


def test_reserve_skips_score_off_trial(monkeypatch: pytest.MonkeyPatch) -> None:
    # Вне триала score не гейтится (ledger не трогаем, статьи не застревают в extracted).
    tenant = SimpleNamespace(
        id=uuid.uuid4(), ai_budget_usd_month=Decimal("10"), subscription_status=None
    )
    called = {"reserve": False}
    monkeypatch.setattr(
        llm_client, "reserve_budget", lambda *a, **k: called.__setitem__("reserve", True) or True
    )
    reservation = llm_client._reserve_budget(
        tenant_id=str(tenant.id), stage="score", session_factory=_trial_factory(tenant)
    )
    assert reservation is None
    assert called["reserve"] is False


def test_reserve_raises_on_expired_trial(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant = SimpleNamespace(
        id=uuid.uuid4(),
        ai_budget_usd_month=Decimal("3"),
        subscription_status="trialing",
        trial_ends_at=datetime.now(UTC) - timedelta(hours=1),
    )
    monkeypatch.setattr(llm_client, "reserve_budget", lambda *a, **k: True)
    with pytest.raises(TrialExpiredError):
        llm_client._reserve_budget(
            tenant_id=str(tenant.id), stage="draft", session_factory=_trial_factory(tenant)
        )
