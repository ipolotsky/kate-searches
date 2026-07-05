"""Конфигурация сервиса из окружения."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:54322/postgres"
    redis_url: str = "redis://localhost:6379/0"

    supabase_url: str = ""
    supabase_service_role_key: str = ""

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Двухуровневый роутинг моделей (главный рычаг юнит-экономики)
    llm_model_score: str = "gemini/gemini-2.0-flash-lite"
    llm_model_draft: str = "openai/gpt-5-mini"

    # Лимит вывода стадии draft. DraftPost (тело ~2k + faq + json_ld + suggested_titles) не влезает
    # в дефолтные 2048. Плюс gpt-5-mini — reasoning-модель: reasoning-токены тоже идут в этот лимит,
    # поэтому нужен запас (иначе finish_reason='length' -> IncompleteOutputException у Instructor).
    llm_draft_max_tokens: int = 16384

    # LiteLLM self-host proxy: если base_url задан, вызовы роутятся через него
    # (per-tenant виртуальные ключи/бюджеты). По умолчанию — прямой SDK-вызов.
    litellm_base_url: str = ""
    litellm_master_key: str = ""

    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3001"

    firecrawl_api_key: str = ""

    # Ingestion (M1): identifiable UA, таймауты и троттлинг скрапинга.
    user_agent: str = "KateSearchesBot/1.0 (+https://katesearches.com/bot)"
    fetch_timeout_seconds: float = 15.0
    default_rate_limit_rpm: int = 60
    robots_cache_ttl_seconds: int = 3600
    extract_body_min_chars: int = 500
    near_dup_hamming_threshold: int = 3
    firecrawl_cost_per_call_usd: float = 0.002
    ingestion_guards_enabled: bool = True
    pipeline_run_stale_minutes: int = 30


settings = Settings()
