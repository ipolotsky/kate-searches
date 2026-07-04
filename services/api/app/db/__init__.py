"""БД-слой: движок/сессии + ORM-модели под схему 0001_init.sql."""

from app.db.engine import engine, get_session, session_scope
from app.db.models import (
    AiUsage,
    Article,
    ArticleSource,
    Base,
    BrandProfile,
    Feedback,
    PipelineRun,
    Post,
    Source,
    SourceSecret,
    Tenant,
    User,
)
from app.db.repositories import (
    ArticleRepository,
    PipelineRunRepository,
    SourceRepository,
    insert_ai_usage,
)

__all__ = [
    "engine",
    "get_session",
    "session_scope",
    "Base",
    "Tenant",
    "User",
    "BrandProfile",
    "Source",
    "Article",
    "ArticleSource",
    "PipelineRun",
    "SourceSecret",
    "Post",
    "Feedback",
    "AiUsage",
    "insert_ai_usage",
    "ArticleRepository",
    "SourceRepository",
    "PipelineRunRepository",
]
