"""ORM-модели покрывают схему 0001_init.sql (без обращения к БД)."""

from app.db.models import Base

EXPECTED_TABLES = {
    "tenants",
    "users",
    "brand_profiles",
    "products",
    "sources",
    "articles",
    "posts",
    "feedback",
    "ai_usage",
}


def test_models_cover_all_tables() -> None:
    assert set(Base.metadata.tables.keys()) == EXPECTED_TABLES


def test_ai_usage_has_metering_columns() -> None:
    columns = {c.name for c in Base.metadata.tables["ai_usage"].columns}
    assert {
        "tenant_id",
        "user_id",
        "stage",
        "model",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "request_id",
    } <= columns
