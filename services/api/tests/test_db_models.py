"""ORM-модели покрывают схему 0001_init.sql (без обращения к БД)."""

from app.db.models import Base

EXPECTED_TABLES = {
    "tenants",
    "users",
    "brand_profiles",
    "sources",
    "articles",
    "posts",
    "feedback",
    "ai_usage",
    "article_sources",
    "pipeline_runs",
    "source_secrets",
    "email_preferences",
    "email_suppression",
    "email_dispatch_log",
}


def test_articles_metadata_mapped_without_clobbering_declarative() -> None:
    columns = {c.name for c in Base.metadata.tables["articles"].columns}
    assert "metadata" in columns
    assert {"duplicate_of", "last_pipeline_run_id"} <= columns


def test_pipeline_runs_has_typed_counters() -> None:
    columns = {c.name for c in Base.metadata.tables["pipeline_runs"].columns}
    assert {"fetched", "new", "duplicated", "extracted", "failed", "run_date", "mode"} <= columns


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
