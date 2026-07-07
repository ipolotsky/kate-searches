"""Hard-cap на /internal/pipeline/generate: при spent>=budget генерация не ставится в очередь."""

import contextlib
import uuid
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.worker.tasks as tasks
from app.db.repositories import ArticleRepository
from app.main import app

client = TestClient(app)


class _FakeSession:
    def __init__(self, tenant):
        self._tenant = tenant

    def get(self, model, primary_key):
        return self._tenant


def _fake_scope(session):
    @contextlib.contextmanager
    def scope():
        yield session

    return scope


def test_generate_blocks_when_budget_exceeded(monkeypatch):
    tenant = SimpleNamespace(ai_budget_usd_month=Decimal("10"))
    monkeypatch.setattr("app.api.routes.session_scope", _fake_scope(_FakeSession(tenant)))
    monkeypatch.setattr("app.api.routes.tenant_month_spend", lambda *a, **k: Decimal("10"))
    monkeypatch.setattr(
        ArticleRepository, "scored_articles", staticmethod(lambda *a, **k: [uuid.uuid4()])
    )
    called = {"delay": False}
    monkeypatch.setattr(
        tasks.run_tenant_generation, "delay", lambda *a, **k: called.__setitem__("delay", True)
    )

    response = client.post("/internal/pipeline/generate", json={"tenant_id": str(uuid.uuid4())})
    body = response.json()

    assert response.status_code == 200
    assert body["queued"] is False
    assert body["budget_exceeded"] is True
    assert body["detail"] == "budget_exceeded"
    assert called["delay"] is False


def test_generate_enqueues_when_within_budget(monkeypatch):
    tenant = SimpleNamespace(ai_budget_usd_month=Decimal("10"))
    monkeypatch.setattr("app.api.routes.session_scope", _fake_scope(_FakeSession(tenant)))
    monkeypatch.setattr("app.api.routes.tenant_month_spend", lambda *a, **k: Decimal("1"))
    monkeypatch.setattr(
        ArticleRepository, "scored_articles", staticmethod(lambda *a, **k: [uuid.uuid4()])
    )
    called = {}
    monkeypatch.setattr(
        tasks.run_tenant_generation,
        "delay",
        lambda *a, **k: called.__setitem__("delay", (a, k)),
    )

    response = client.post("/internal/pipeline/generate", json={"tenant_id": str(uuid.uuid4())})
    body = response.json()

    assert response.status_code == 200
    assert body["queued"] is True
    assert body["budget_exceeded"] is False
    assert "delay" in called


def test_generate_no_scored_articles_returns_zero(monkeypatch):
    tenant = SimpleNamespace(ai_budget_usd_month=Decimal("10"))
    monkeypatch.setattr("app.api.routes.session_scope", _fake_scope(_FakeSession(tenant)))
    monkeypatch.setattr("app.api.routes.tenant_month_spend", lambda *a, **k: Decimal("1"))
    monkeypatch.setattr(ArticleRepository, "scored_articles", staticmethod(lambda *a, **k: []))
    monkeypatch.setattr(
        tasks.run_tenant_generation, "delay", lambda *a, **k: (_ for _ in ()).throw(AssertionError)
    )

    response = client.post("/internal/pipeline/generate", json={"tenant_id": str(uuid.uuid4())})
    body = response.json()

    assert body["queued"] is False
    assert body["count"] == 0
    assert body["budget_exceeded"] is False
