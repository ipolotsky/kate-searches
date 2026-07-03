"""Общие фикстуры и гейтинг тестов.

integration — требуют запущенный Supabase CLI стек и RUN_DB_TESTS=1.
live — требуют реальный ключ провайдера и RUN_LIVE_LLM=1.
Без флагов такие тесты скипаются, чтобы `make test` был зелёным в CI без инфры.
"""

import os

import pytest

DEFAULT_DB_URL = "postgresql://postgres:postgres@localhost:54322/postgres"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DB_URL)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_db = bool(os.environ.get("RUN_DB_TESTS"))
    run_live = bool(os.environ.get("RUN_LIVE_LLM"))
    skip_db = pytest.mark.skip(reason="нужен Supabase CLI стек и RUN_DB_TESTS=1")
    skip_live = pytest.mark.skip(reason="нужен ключ провайдера и RUN_LIVE_LLM=1")
    for item in items:
        if "integration" in item.keywords and not run_db:
            item.add_marker(skip_db)
        if "live" in item.keywords and not run_live:
            item.add_marker(skip_live)
