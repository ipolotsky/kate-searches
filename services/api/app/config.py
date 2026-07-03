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

    # LiteLLM self-host proxy: если base_url задан, вызовы роутятся через него
    # (per-tenant виртуальные ключи/бюджеты). По умолчанию — прямой SDK-вызов.
    litellm_base_url: str = ""
    litellm_master_key: str = ""

    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3001"

    firecrawl_api_key: str = ""


settings = Settings()
