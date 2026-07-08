"""Высокоуровневые уведомления: контент (ru/en) + сбор получателей -> send_email (идемпотентно).

Digest/trial-ending/budget-threshold шлём всем пользователям тенанта на их locale; welcome — одному
зарегистрировавшемуся. Всё безопасно к повтору: dedup_key в email_dispatch_log режет дубли.
"""

import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.engine import session_scope
from app.db.models import User
from app.email.client import send_email

SessionFactory = Callable[[], AbstractContextManager[Session]]


def _url(path: str) -> str:
    return f"{settings.app_base_url}{path}"


def _norm_locale(locale: str | None) -> str:
    return locale if locale in ("en", "ru") else "en"


def _uuid(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _tenant_recipients(session: Session, tenant_id: uuid.UUID) -> list[tuple[uuid.UUID, str, str]]:
    rows = session.execute(
        select(User.id, User.email, User.locale).where(User.tenant_id == tenant_id)
    )
    return [(row[0], row[1], _norm_locale(row[2])) for row in rows]


def send_welcome(
    *,
    user_id,
    tenant_id,
    email: str,
    locale: str,
    session_factory: SessionFactory = session_scope,
) -> None:
    locale = _norm_locale(locale)
    content = _welcome(locale)
    send_email(
        category="transactional",
        notification_type="welcome",
        tenant_id=_uuid(tenant_id),
        user_id=_uuid(user_id),
        to_email=email,
        locale=locale,
        dedup_key="welcome",
        subject=content["subject"],
        title=content["title"],
        lines=content["lines"],
        cta_label=content["cta"],
        cta_url=_url(f"/{locale}/dashboard"),
        session_factory=session_factory,
    )


def send_digest(
    *,
    tenant_id,
    run_id,
    selected: int,
    matches: int,
    session_factory: SessionFactory = session_scope,
) -> int:
    """Дайджест всем пользователям тенанта. dedup_key = run_id (один digest на прогон на юзера)."""
    tenant_uuid = _uuid(tenant_id)
    with session_factory() as session:
        recipients = _tenant_recipients(session, tenant_uuid)
    sent = 0
    for user_id, email, locale in recipients:
        content = _digest(locale, selected=selected, matches=matches)
        result = send_email(
            category="digest",
            notification_type="digest",
            tenant_id=tenant_uuid,
            user_id=user_id,
            to_email=email,
            locale=locale,
            dedup_key=str(run_id),
            subject=content["subject"],
            title=content["title"],
            lines=content["lines"],
            cta_label=content["cta"],
            cta_url=_url(f"/{locale}/dashboard"),
            session_factory=session_factory,
        )
        if result is not None:
            sent += 1
    return sent


def send_trial_ending(
    *,
    tenant_id,
    days: int,
    dedup_key: str,
    session_factory: SessionFactory = session_scope,
) -> int:
    tenant_uuid = _uuid(tenant_id)
    with session_factory() as session:
        recipients = _tenant_recipients(session, tenant_uuid)
    sent = 0
    for user_id, email, locale in recipients:
        content = _trial_ending(locale, days=days)
        result = send_email(
            category="transactional",
            notification_type="trial_ending",
            tenant_id=tenant_uuid,
            user_id=user_id,
            to_email=email,
            locale=locale,
            dedup_key=dedup_key,
            subject=content["subject"],
            title=content["title"],
            lines=content["lines"],
            cta_label=content["cta"],
            cta_url=_url(f"/{locale}/billing"),
            session_factory=session_factory,
        )
        if result is not None:
            sent += 1
    return sent


def send_budget_threshold(
    *,
    tenant_id,
    pct: int,
    dedup_key: str,
    session_factory: SessionFactory = session_scope,
) -> int:
    tenant_uuid = _uuid(tenant_id)
    with session_factory() as session:
        recipients = _tenant_recipients(session, tenant_uuid)
    sent = 0
    for user_id, email, locale in recipients:
        content = _budget_threshold(locale, pct=pct)
        result = send_email(
            category="transactional",
            notification_type="budget_threshold",
            tenant_id=tenant_uuid,
            user_id=user_id,
            to_email=email,
            locale=locale,
            dedup_key=dedup_key,
            subject=content["subject"],
            title=content["title"],
            lines=content["lines"],
            cta_label=content["cta"],
            cta_url=_url(f"/{locale}/billing"),
            session_factory=session_factory,
        )
        if result is not None:
            sent += 1
    return sent


# ─────────────────────────────────────────── Контент (ru/en)


def _welcome(locale: str) -> dict:
    if locale == "ru":
        return {
            "subject": "Добро пожаловать в KateSearches",
            "title": "Рады видеть",
            "lines": [
                "Настройте источники и голос бренда, затем начните бесплатный триал — "
                "и получите первые черновики.",
                "Мы мониторим новости в вашей нише и превращаем лучшие инфоповоды "
                "в SEO-черновики в голосе бренда.",
            ],
            "cta": "Открыть дашборд",
        }
    return {
        "subject": "Welcome to KateSearches",
        "title": "Welcome aboard",
        "lines": [
            "Set up your sources and brand voice, then start your free trial "
            "to generate your first drafts.",
            "We monitor the news in your niche and turn the best stories into on-brand SEO drafts.",
        ],
        "cta": "Open dashboard",
    }


def _digest(locale: str, *, selected: int, matches: int) -> dict:
    if locale == "ru":
        match_line = (
            f"{matches} из них — сильное попадание и готовы к черновику."
            if matches
            else "Сильных попаданий сегодня нет — продолжаем следить."
        )
        return {
            "subject": f"Сегодня: {selected} статей, {matches} в точку",
            "title": "Дайджест за сегодня",
            "lines": [f"Сегодня для вас отобрано {selected} статей.", match_line],
            "cta": "Открыть дашборд",
        }
    match_line = (
        f"{matches} are a strong match and ready to draft."
        if matches
        else "No strong matches today — we'll keep watching."
    )
    return {
        "subject": f"Today: {selected} articles, {matches} great matches",
        "title": "Your daily digest",
        "lines": [f"We scored {selected} articles for you today.", match_line],
        "cta": "Open dashboard",
    }


def _trial_ending(locale: str, *, days: int) -> dict:
    if locale == "ru":
        return {
            "subject": f"Триал заканчивается через {days} дн.",
            "title": "Триал скоро закончится",
            "lines": [
                f"Ваш бесплатный триал заканчивается через {days} дн.",
                "Оформите тариф, чтобы генерация не прерывалась.",
            ],
            "cta": "Выбрать тариф",
        }
    return {
        "subject": f"Your trial ends in {days} days",
        "title": "Trial ending soon",
        "lines": [
            f"Your free trial ends in {days} days.",
            "Upgrade to keep generating drafts without interruption.",
        ],
        "cta": "Choose a plan",
    }


def _budget_threshold(locale: str, *, pct: int) -> dict:
    if locale == "ru":
        return {
            "subject": f"Использовано {pct}% бюджета",
            "title": "Обновление по бюджету",
            "lines": [
                f"Вы израсходовали {pct}% месячного бюджета.",
                "Перейдите на старший тариф для большего объёма.",
            ],
            "cta": "Управление тарифом",
        }
    return {
        "subject": f"You've used {pct}% of your budget",
        "title": "Budget update",
        "lines": [
            f"You've used {pct}% of your monthly budget.",
            "Upgrade to a higher plan for more headroom.",
        ],
        "cta": "Manage plan",
    }
