"""Валидация пилотных данных LOOTON и идемпотентности сида — без сети/БД."""

import importlib.util
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.db.models import BrandProfile, Source, Tenant, User
from app.models.scoring import CriterionScore, RelevanceScore
from app.pipeline import generation

DATA_PATH = Path(__file__).parents[1] / "scripts" / "looton_seed.json"
SEED_PATH = Path(__file__).parents[1] / "scripts" / "seed_looton.py"


def _load_seed_module() -> object:
    spec = importlib.util.spec_from_file_location("seed_looton", SEED_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed_looton = _load_seed_module()


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> list:
        return list(self._rows)

    def scalar_one_or_none(self) -> object | None:
        return self._rows[0] if self._rows else None


class _FakeSession:
    """Маршрутизирует select(...) по ORM-сущности; фиксирует add/flush. Без БД."""

    def __init__(self, rows: dict | None = None) -> None:
        self._rows = rows or {}
        self.added: list = []
        self.flushes = 0

    def execute(self, stmt: object) -> _FakeResult:
        entity = stmt.column_descriptions[0]["entity"]
        return _FakeResult(self._rows.get(entity, []))

    def get(self, model: object, ident: object) -> object | None:
        for row in self._rows.get(model, []):
            if getattr(row, "id", None) == ident:
                return row
        return None

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushes += 1


@pytest.fixture(scope="module")
def data() -> dict:
    with DATA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def test_tenant_is_russian(data: dict) -> None:
    tenant = data["tenant"]
    assert tenant["name"] == "LOOTON"
    assert tenant["default_locale"] == "ru"
    assert tenant["timezone"]
    assert isinstance(tenant["pipeline_hour_local"], int)


def test_brand_profile_shape(data: dict) -> None:
    profile = data["brand_profile"]
    assert profile["locales"] == ["ru"]
    assert isinstance(profile["score_threshold"], int)
    assert profile["score_threshold"] > 60  # калибровка: строже дефолта
    assert profile["company_description"]
    assert profile["audience_description"]
    assert profile["filter_criteria"]
    assert profile["criteria_weights"]["resale_potential"] >= 1.5  # ресейл весит больше
    assert profile["voice_config"]["tone"]
    assert profile["voice_config"]["unique_angle_hint"]


def test_voice_examples_format(data: dict) -> None:
    examples = data["brand_profile"]["voice_examples"]
    assert len(examples) >= 5
    for example in examples:
        assert set(example.keys()) == {"source_url", "why", "post_text"}
        assert example["post_text"].strip()
        assert example["why"].strip()
        assert isinstance(example["source_url"], str)
    for example in examples[:3]:  # первые 3 идут в промпт — у них должен быть инфоповод
        assert example["source_url"].startswith("http")


def test_voice_examples_have_no_mojibake(data: dict) -> None:
    blob = json.dumps(data["brand_profile"]["voice_examples"], ensure_ascii=False)
    assert "�" not in blob  # U+FFFD — маркер битой кодировки, из-за него был блокер M6


def test_sources_are_eleven_valid_rss(data: dict) -> None:
    sources = data["sources"]
    assert len(sources) == 11
    for source in sources:
        assert source["type"] == "rss"
        assert source["url"].startswith("http")
        assert source["title"].strip()
        assert 1 <= source["priority"] <= 5


def test_format_examples_renders_infopovod_for_real_data(data: dict) -> None:
    formatted = generation._format_examples(data["brand_profile"]["voice_examples"])
    assert "Инфоповод: http" in formatted
    assert "Пост:" in formatted


def test_criteria_weights_match_relevance_criteria(data: dict) -> None:
    criterion_fields = {
        name
        for name, field in RelevanceScore.model_fields.items()
        if field.annotation is CriterionScore
    }
    weights = data["brand_profile"]["criteria_weights"]
    unknown = set(weights) - criterion_fields
    assert not unknown, f"веса на несуществующие критерии (уйдут молча): {unknown}"


def _brand_spec(data: dict) -> dict:
    return data["brand_profile"]


def test_resolve_tenant_reuses_existing_by_name(data: dict) -> None:
    existing = Tenant(name="LOOTON")
    session = _FakeSession({Tenant: [existing]})
    tenant, is_new = seed_looton.resolve_tenant(
        session, data["tenant"], owner_email=None, tenant_id=None, create=False
    )
    assert tenant is existing
    assert is_new is False
    assert session.added == []  # существующий не пересоздан


def test_resolve_tenant_fail_loud_when_missing_without_create(data: dict) -> None:
    session = _FakeSession({Tenant: []})
    with pytest.raises(RuntimeError, match="не найден"):
        seed_looton.resolve_tenant(
            session, data["tenant"], owner_email=None, tenant_id=None, create=False
        )
    assert session.added == []  # orphan-тенант НЕ создан молча


def test_resolve_tenant_creates_only_with_flag(data: dict) -> None:
    session = _FakeSession({Tenant: []})
    tenant, is_new = seed_looton.resolve_tenant(
        session, data["tenant"], owner_email=None, tenant_id=None, create=True
    )
    assert is_new is True
    assert tenant in session.added


def test_resolve_tenant_rejects_ambiguous_name(data: dict) -> None:
    session = _FakeSession({Tenant: [Tenant(name="LOOTON"), Tenant(name="LOOTON")]})
    with pytest.raises(RuntimeError, match="Найдено 2"):
        seed_looton.resolve_tenant(
            session, data["tenant"], owner_email=None, tenant_id=None, create=False
        )


def test_resolve_tenant_by_owner_email(data: dict) -> None:
    tid = uuid.uuid4()
    tenant = Tenant(name="whatever the operator typed")
    tenant.id = tid
    user = SimpleNamespace(email="kate@looton.com", tenant_id=tid)
    session = _FakeSession({User: [user], Tenant: [tenant]})
    resolved, is_new = seed_looton.resolve_tenant(
        session, data["tenant"], owner_email="kate@looton.com", tenant_id=None, create=False
    )
    assert resolved is tenant  # имя тенанта роли не играет — резолв по владельцу
    assert is_new is False


def test_upsert_brand_profile_creates_then_keeps(data: dict) -> None:
    tid = uuid.uuid4()
    empty = _FakeSession({BrandProfile: []})
    assert seed_looton.upsert_brand_profile(empty, tid, _brand_spec(data), force=False) == "created"
    assert len(empty.added) == 1

    tuned = SimpleNamespace(score_threshold=99)
    with_profile = _FakeSession({BrandProfile: [tuned]})
    status = seed_looton.upsert_brand_profile(with_profile, tid, _brand_spec(data), force=False)
    assert status == "kept"
    assert tuned.score_threshold == 99  # калибровка оператора не затёрта
    assert with_profile.added == []


def test_upsert_brand_profile_force_overwrites(data: dict) -> None:
    tid = uuid.uuid4()
    tuned = SimpleNamespace(score_threshold=99)
    session = _FakeSession({BrandProfile: [tuned]})
    status = seed_looton.upsert_brand_profile(session, tid, _brand_spec(data), force=True)
    assert status == "overwritten"
    assert tuned.score_threshold == data["brand_profile"]["score_threshold"]


def test_upsert_sources_adds_missing_and_is_idempotent(data: dict) -> None:
    tid = uuid.uuid4()
    empty = _FakeSession({Source: []})
    created, overwritten = seed_looton.upsert_sources(empty, tid, data["sources"], force=False)
    assert created == len(data["sources"])
    assert overwritten == 0

    all_existing = [SimpleNamespace(url=spec["url"], enabled=False) for spec in data["sources"]]
    rerun = _FakeSession({Source: all_existing})
    created2, overwritten2 = seed_looton.upsert_sources(rerun, tid, data["sources"], force=False)
    assert created2 == 0  # повтор не плодит дубли
    assert overwritten2 == 0
    assert rerun.added == []
    # выключенный оператором источник не включается обратно без --force
    assert all(src.enabled is False for src in all_existing)


def test_upsert_sources_force_overwrites_existing(data: dict) -> None:
    tid = uuid.uuid4()
    disabled = SimpleNamespace(url=data["sources"][0]["url"], enabled=False)
    session = _FakeSession({Source: [disabled]})
    created, overwritten = seed_looton.upsert_sources(
        session, tid, [data["sources"][0]], force=True
    )
    assert created == 0
    assert overwritten == 1
    assert disabled.enabled is True
