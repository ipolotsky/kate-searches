"""Идемпотентный сид пилота LOOTON (M6): тенант + бренд-профиль + источники.

Данные — в scripts/looton_seed.json (правит Kate). Пишет под service_role (bypassrls) через
session_scope, как весь пайплайн.

Таргетинг тенанта (важно: имя тенанта — свободный текст из регистрации, по нему НЕ матчим молча):
- прод: --owner-email EMAIL (тенант резолвится по владельцу) или --tenant-id UUID;
- чистая БД / headless: --create (создать тенант из JSON name);
- без флагов существующий тенант ищется по имени, и если не найден — падаем с ошибкой (fail loud),
  а не создаём orphan-тенант.

Идемпотентность: по умолчанию create-only — существующие профиль/источники НЕ трогаются
(калибровка оператора в UI сохраняется). --force перезаписывает их из JSON.

Запуск (прод): DATABASE_URL=... python scripts/seed_looton.py --owner-email kate@looton.com
Запуск (чистая БД): DATABASE_URL=... python scripts/seed_looton.py --create
"""

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.engine import session_scope
from app.db.models import BrandProfile, Source, Tenant, User

DATA_PATH = Path(__file__).parent / "looton_seed.json"

_TENANT_FIELDS = ("default_locale", "timezone", "pipeline_hour_local")
_BRAND_FIELDS = (
    "company_description",
    "audience_description",
    "filter_criteria",
    "criteria_weights",
    "score_threshold",
    "locales",
    "voice_config",
    "voice_examples",
)
_SOURCE_FIELDS = ("type", "title", "priority", "category")


def load_data() -> dict[str, Any]:
    with DATA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def resolve_tenant(
    session: Session,
    spec: dict[str, Any],
    *,
    owner_email: str | None,
    tenant_id: uuid.UUID | None,
    create: bool,
) -> tuple[Tenant, bool]:
    """Найти целевой тенант детерминированно. Возвращает (tenant, is_new)."""
    if tenant_id is not None:
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            raise RuntimeError(f"Тенант с id {tenant_id} не найден.")
        return tenant, False
    if owner_email is not None:
        user = session.execute(select(User).where(User.email == owner_email)).scalar_one_or_none()
        if user is None:
            raise RuntimeError(
                f"Пользователь {owner_email!r} не найден — сначала регистрация тенанта в web."
            )
        tenant = session.get(Tenant, user.tenant_id)
        if tenant is None:
            raise RuntimeError(f"У пользователя {owner_email!r} нет привязанного тенанта.")
        return tenant, False
    name = spec["name"]
    rows = list(session.execute(select(Tenant).where(Tenant.name == name)).scalars())
    if len(rows) > 1:
        raise RuntimeError(
            f"Найдено {len(rows)} тенантов с именем {name!r}. "
            "Таргетируй по --owner-email или --tenant-id."
        )
    if rows:
        return rows[0], False
    if not create:
        raise RuntimeError(
            f"Тенант {name!r} не найден. Для существующего укажи --owner-email или --tenant-id; "
            "для чистой БД добавь --create."
        )
    tenant = Tenant(name=name)
    session.add(tenant)
    session.flush()
    return tenant, True


def upsert_brand_profile(
    session: Session, tenant_id: uuid.UUID, spec: dict[str, Any], *, force: bool
) -> str:
    """Создать бренд-профиль. Существующий не трогаем (сохраняем калибровку), кроме --force."""
    profile = session.execute(
        select(BrandProfile).where(BrandProfile.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if profile is None:
        profile = BrandProfile(tenant_id=tenant_id)
        for field in _BRAND_FIELDS:
            setattr(profile, field, spec[field])
        session.add(profile)
        session.flush()
        return "created"
    if not force:
        return "kept"
    for field in _BRAND_FIELDS:
        setattr(profile, field, spec[field])
    session.flush()
    return "overwritten"


def upsert_sources(
    session: Session, tenant_id: uuid.UUID, specs: list[dict[str, Any]], *, force: bool
) -> tuple[int, int]:
    """Добавить недостающие источники по url. Существующие не трогаем, кроме --force."""
    existing = {
        source.url: source
        for source in session.execute(select(Source).where(Source.tenant_id == tenant_id)).scalars()
    }
    created = 0
    overwritten = 0
    for spec in specs:
        source = existing.get(spec["url"])
        if source is None:
            source = Source(tenant_id=tenant_id, url=spec["url"], enabled=True)
            for field in _SOURCE_FIELDS:
                setattr(source, field, spec[field])
            session.add(source)
            created += 1
        elif force:
            for field in _SOURCE_FIELDS:
                setattr(source, field, spec[field])
            source.enabled = True
            overwritten += 1
    session.flush()
    return created, overwritten


def seed(
    *,
    owner_email: str | None = None,
    tenant_id: uuid.UUID | None = None,
    create: bool = False,
    force: bool = False,
) -> None:
    data = load_data()
    with session_scope() as session:
        tenant, is_new = resolve_tenant(
            session, data["tenant"], owner_email=owner_email, tenant_id=tenant_id, create=create
        )
        if is_new or force:
            for field in _TENANT_FIELDS:
                setattr(tenant, field, data["tenant"][field])
            session.flush()
        brand_status = upsert_brand_profile(session, tenant.id, data["brand_profile"], force=force)
        created, overwritten = upsert_sources(session, tenant.id, data["sources"], force=force)
        kept = len(data["sources"]) - created - overwritten
        examples = len(data["brand_profile"]["voice_examples"])
        print(
            f"LOOTON seed: tenant={tenant.id} ({'new' if is_new else 'existing'}) "
            f"locale={tenant.default_locale} brand_profile={brand_status} "
            f"examples={examples} sources(new={created} force={overwritten} kept={kept})"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Идемпотентный сид пилота LOOTON (M6).")
    parser.add_argument("--owner-email", help="таргетировать тенант по email владельца (прод)")
    parser.add_argument("--tenant-id", help="таргетировать тенант по явному UUID")
    parser.add_argument(
        "--create", action="store_true", help="создать тенант из JSON name, если не найден"
    )
    parser.add_argument(
        "--force", action="store_true", help="перезаписать существующие профиль/источники из JSON"
    )
    args = parser.parse_args()
    parsed_tenant_id = uuid.UUID(args.tenant_id) if args.tenant_id else None
    seed(
        owner_email=args.owner_email,
        tenant_id=parsed_tenant_id,
        create=args.create,
        force=args.force,
    )


if __name__ == "__main__":
    main()
