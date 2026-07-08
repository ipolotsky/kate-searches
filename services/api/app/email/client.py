"""Отправка email через Resend с идемпотентностью, suppression и per-type согласием.

Пусто RESEND_API_KEY => email выключен (dev/тесты не шлют, вернём None). Идемпотентность durable
через email_dispatch_log (insert-before-send), плюс Resend Idempotency-Key как быстрый доп. гард.
Pre-send фильтр: suppression (bounce/complaint) + digest opt-out.
"""

import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session

from app.config import settings
from app.db.engine import session_scope
from app.db.repositories import EmailRepository
from app.email.templates import render_html

SessionFactory = Callable[[], AbstractContextManager[Session]]


def unsubscribe_url(token: uuid.UUID) -> str:
    # Путь под /api — вне locale/auth-middleware web, публично доступен для one-click отписки.
    return f"{settings.app_base_url}/api/unsubscribe?token={token}"


def _list_unsubscribe_headers(token: uuid.UUID) -> dict[str, str]:
    return {
        "List-Unsubscribe": f"<{unsubscribe_url(token)}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def _resend_send(
    *, to: str, subject: str, html: str, headers: dict[str, str] | None, idempotency_key: str
) -> str | None:
    import resend

    resend.api_key = settings.resend_api_key
    params: dict = {"from": settings.email_from, "to": [to], "subject": subject, "html": html}
    if headers:
        params["headers"] = headers
    result = resend.Emails.send(params, {"idempotency_key": idempotency_key})
    if isinstance(result, dict):
        return result.get("id")
    return getattr(result, "id", None)


def send_email(
    *,
    category: str,
    notification_type: str,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    to_email: str,
    locale: str,
    dedup_key: str,
    subject: str,
    title: str,
    lines: list[str],
    cta_label: str | None = None,
    cta_url: str | None = None,
    session_factory: SessionFactory = session_scope,
) -> str | None:
    """Послать письмо. None — не отправлено (выключено / suppressed / opt-out / дубль).

    category: 'digest' (respects opt-out + List-Unsubscribe) | 'transactional' (сервисное).
    """
    if not settings.resend_api_key:
        return None
    email_norm = to_email.strip().lower()

    with session_factory() as session:
        if EmailRepository.is_suppressed(session, email_norm):
            return None
        prefs = EmailRepository.get_or_create_preferences(
            session, user_id=user_id, tenant_id=tenant_id
        )
        if category == "digest" and not prefs.digest_enabled:
            return None
        if not EmailRepository.claim_dispatch(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=notification_type,
            dedup_key=dedup_key,
        ):
            return None
        token = prefs.unsubscribe_token

    unsub = unsubscribe_url(token) if category == "digest" else None
    html = render_html(
        locale=locale,
        title=title,
        lines=lines,
        cta_label=cta_label,
        cta_url=cta_url,
        unsubscribe_url=unsub,
    )
    headers = _list_unsubscribe_headers(token) if category == "digest" else None

    try:
        resend_id = _resend_send(
            to=to_email,
            subject=subject,
            html=html,
            headers=headers,
            idempotency_key=f"{notification_type}:{user_id}:{dedup_key}",
        )
    except Exception:
        with session_factory() as session:
            EmailRepository.release_dispatch(
                session,
                user_id=user_id,
                notification_type=notification_type,
                dedup_key=dedup_key,
            )
        raise

    with session_factory() as session:
        EmailRepository.mark_dispatch_sent(
            session,
            user_id=user_id,
            notification_type=notification_type,
            dedup_key=dedup_key,
            resend_email_id=resend_id,
        )
    return resend_id or ""
