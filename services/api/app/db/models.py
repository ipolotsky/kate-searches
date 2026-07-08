"""SQLAlchemy ORM-модели под supabase/migrations/0001_init.sql.

Имена таблиц и колонок совпадают со схемой 1:1. Это модель данных для api;
Pydantic-схемы в app/models/ остаются контрактами пайплайна.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text)
    plan: Mapped[str] = mapped_column(Text, server_default=text("'pilot'"))
    ai_budget_usd_month: Mapped[Decimal] = mapped_column(Numeric, server_default=text("15"))
    ai_spent_usd_month: Mapped[Decimal] = mapped_column(Numeric, server_default=text("0"))
    upsell_threshold_pct: Mapped[int] = mapped_column(Integer, server_default=text("80"))
    default_locale: Mapped[str] = mapped_column(Text, server_default=text("'en'"))
    timezone: Mapped[str] = mapped_column(Text, server_default=text("'UTC'"))
    pipeline_hour_local: Mapped[int] = mapped_column(SmallInteger, server_default=text("6"))
    stripe_customer_id: Mapped[str | None] = mapped_column(Text)
    stripe_subscription_id: Mapped[str | None] = mapped_column(Text)
    subscription_status: Mapped[str | None] = mapped_column(Text)
    current_period_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    trial_ends_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    billing_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    trial_drafts_limit: Mapped[int | None] = mapped_column(Integer)
    trial_sources_limit: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    email: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, server_default=text("'editor'"))
    locale: Mapped[str] = mapped_column(Text, server_default=text("'en'"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class BrandProfile(Base):
    __tablename__ = "brand_profiles"
    __table_args__ = (UniqueConstraint("tenant_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    company_description: Mapped[str | None] = mapped_column(Text)
    audience_description: Mapped[str | None] = mapped_column(Text)
    filter_criteria: Mapped[str | None] = mapped_column(Text)
    voice_config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    voice_examples: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    criteria_weights: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    score_threshold: Mapped[int] = mapped_column(Integer, server_default=text("60"))
    locales: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{en}'"))
    files: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, server_default=text("3"))
    category: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    state: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    last_run_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_status: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_error_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("tenant_id", "canonical_url"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL")
    )
    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    media: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    content_hash: Mapped[str | None] = mapped_column(Text)
    simhash: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(Text, server_default=text("'new'"))
    status_changed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    relevance: Mapped[dict | None] = mapped_column(JSONB)
    relevance_score: Mapped[int | None] = mapped_column(Integer)
    doc_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL")
    )
    last_pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL")
    )
    title: Mapped[str | None] = mapped_column(Text)
    body_markdown: Mapped[str | None] = mapped_column(Text)
    faq: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    json_ld: Mapped[dict | None] = mapped_column(JSONB)
    seo: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    suggested_titles: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    language: Mapped[str | None] = mapped_column(Text)
    ai_model: Mapped[str | None] = mapped_column(Text)
    ai_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric)
    status: Mapped[str] = mapped_column(Text, server_default=text("'new'"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    target_type: Mapped[str] = mapped_column(Text)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    rating: Mapped[int | None] = mapped_column(Integer)
    edited_diff: Mapped[dict | None] = mapped_column(JSONB)
    comment: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class AiUsage(Base):
    __tablename__ = "ai_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    stage: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric, server_default=text("0"))
    request_id: Mapped[str | None] = mapped_column(Text)
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class ArticleSource(Base):
    __tablename__ = "article_sources"
    __table_args__ = (UniqueConstraint("article_id", "source_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE")
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL")
    )
    external_id: Mapped[str | None] = mapped_column(Text)
    priority_at_seen: Mapped[int | None] = mapped_column(Integer)
    first_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (UniqueConstraint("tenant_id", "run_date", "mode"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    run_date: Mapped[date] = mapped_column(Date)
    mode: Mapped[str] = mapped_column(Text, server_default=text("'incremental'"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'running'"))
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    fetched: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    new: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    duplicated: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    extracted: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    scored: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    filtered_out: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    drafted: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    failed: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    stats: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class EmailPreference(Base):
    __tablename__ = "email_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    digest_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    product_updates_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    unsubscribe_token: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), server_default=text("gen_random_uuid()")
    )
    consent_source: Mapped[str | None] = mapped_column(Text)
    consent_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class EmailSuppression(Base):
    __tablename__ = "email_suppression"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL")
    )
    email: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    source_event_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class EmailDispatchLog(Base):
    __tablename__ = "email_dispatch_log"
    __table_args__ = (UniqueConstraint("user_id", "notification_type", "dedup_key"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    notification_type: Mapped[str] = mapped_column(Text)
    dedup_key: Mapped[str] = mapped_column(Text)
    resend_email_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'sent'"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class SourceSecret(Base):
    __tablename__ = "source_secrets"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    secrets: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
