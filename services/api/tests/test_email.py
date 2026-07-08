"""Email-модуль: рендер layout + send-логика (suppression / digest opt-out / dedup / отправка).

Без сети и БД: EmailRepository и _resend_send замоканы, session_factory — пустой контекст.
"""

import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.email import client as email_client
from app.email import notifications
from app.email.templates import render_html


@contextmanager
def _scope():
    yield SimpleNamespace()


def _kwargs(**override) -> dict:
    base = {
        "category": "digest",
        "notification_type": "digest",
        "tenant_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "to_email": "a@b.co",
        "locale": "en",
        "dedup_key": "run-1",
        "subject": "s",
        "title": "t",
        "lines": ["l"],
        "session_factory": _scope,
    }
    base.update(override)
    return base


def _allow(monkeypatch) -> None:
    monkeypatch.setattr(email_client.settings, "resend_api_key", "re_test")
    monkeypatch.setattr(
        email_client.EmailRepository, "is_suppressed", staticmethod(lambda s, e: False)
    )
    prefs = SimpleNamespace(digest_enabled=True, unsubscribe_token=uuid.uuid4())
    monkeypatch.setattr(
        email_client.EmailRepository,
        "get_or_create_preferences",
        staticmethod(lambda s, **k: prefs),
    )
    monkeypatch.setattr(
        email_client.EmailRepository, "claim_dispatch", staticmethod(lambda s, **k: True)
    )
    monkeypatch.setattr(
        email_client.EmailRepository, "mark_dispatch_sent", staticmethod(lambda s, **k: None)
    )
    monkeypatch.setattr(
        email_client.EmailRepository, "release_dispatch", staticmethod(lambda s, **k: None)
    )


def test_render_html_includes_content_and_unsubscribe() -> None:
    html = render_html(
        locale="en",
        title="Hi",
        lines=["one", "two"],
        cta_label="Go",
        cta_url="https://x.test",
        unsubscribe_url="https://u.test",
    )
    assert "Hi" in html
    assert "one" in html and "two" in html
    assert "https://x.test" in html
    assert "https://u.test" in html and "Unsubscribe" in html


def test_render_html_no_unsubscribe_when_absent() -> None:
    html = render_html(locale="en", title="Hi", lines=["x"])
    assert "Unsubscribe" not in html


def test_send_email_disabled_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_client.settings, "resend_api_key", "")
    assert email_client.send_email(**_kwargs()) is None


def test_send_email_skips_suppressed(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow(monkeypatch)
    monkeypatch.setattr(
        email_client.EmailRepository, "is_suppressed", staticmethod(lambda s, e: True)
    )
    called = {"sent": False}
    monkeypatch.setattr(email_client, "_resend_send", lambda **k: called.__setitem__("sent", True))
    assert email_client.send_email(**_kwargs()) is None
    assert called["sent"] is False


def test_send_email_skips_digest_optout(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow(monkeypatch)
    prefs = SimpleNamespace(digest_enabled=False, unsubscribe_token=uuid.uuid4())
    monkeypatch.setattr(
        email_client.EmailRepository,
        "get_or_create_preferences",
        staticmethod(lambda s, **k: prefs),
    )
    called = {"sent": False}
    monkeypatch.setattr(email_client, "_resend_send", lambda **k: called.__setitem__("sent", True))
    assert email_client.send_email(**_kwargs(category="digest")) is None
    assert called["sent"] is False


def test_send_email_transactional_ignores_digest_optout(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow(monkeypatch)
    prefs = SimpleNamespace(digest_enabled=False, unsubscribe_token=uuid.uuid4())
    monkeypatch.setattr(
        email_client.EmailRepository,
        "get_or_create_preferences",
        staticmethod(lambda s, **k: prefs),
    )
    monkeypatch.setattr(email_client, "_resend_send", lambda **k: "id_1")
    # welcome — transactional, opt-out от digest не мешает
    result = email_client.send_email(
        **_kwargs(category="transactional", notification_type="welcome")
    )
    assert result == "id_1"


def test_send_email_sends_when_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow(monkeypatch)
    captured: dict = {}
    monkeypatch.setattr(email_client, "_resend_send", lambda **k: captured.update(k) or "email_123")
    result = email_client.send_email(**_kwargs())
    assert result == "email_123"
    assert captured["headers"] is not None  # digest несёт List-Unsubscribe


def test_send_email_dedup_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow(monkeypatch)
    monkeypatch.setattr(
        email_client.EmailRepository, "claim_dispatch", staticmethod(lambda s, **k: False)
    )
    called = {"sent": False}
    monkeypatch.setattr(email_client, "_resend_send", lambda **k: called.__setitem__("sent", True))
    assert email_client.send_email(**_kwargs()) is None
    assert called["sent"] is False


def test_digest_content_reports_counts() -> None:
    content = notifications._digest("en", selected=12, matches=3)
    assert "12" in content["subject"]
    assert any("3" in line for line in content["lines"])
