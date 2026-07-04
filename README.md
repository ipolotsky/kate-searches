# KateSearches

SaaS, который превращает поток отраслевых новостей в готовые черновики SEO/AEO-постов, связывающие свежий инфоповод с брендом.

**Как это работает:** мониторим источники клиента → скорим каждую новость по его критериям релевантности → для прошедших отбор генерим черновик в голосе бренда — симбиоз «инфоповод × бренд» (SEO + AEO + JSON-LD) → отдаём в дашборд. Маркетолог правит и публикует.

Первый клиент — **LOOTON** (ресейл-маркетплейс премиум-одежды).

## Стек

| Слой | Технология |
|---|---|
| Фронт | Next.js 15 (App Router), TypeScript, Tailwind + Flowbite React, next-intl (ru/en) |
| AI/пайплайн | FastAPI (Python 3.12), Pydantic v2, Instructor, LiteLLM, Langfuse |
| Сбор данных | feedparser (RSS), Crawl4AI/Firecrawl (скрапинг), trafilatura (экстракция), dlt |
| БД/Auth | Supabase (Postgres + Auth + RLS) |
| Очереди | Celery + Redis |
| CI/CD | GitHub Actions (lint+test → deploy) |

## Быстрый старт

```bash
make up                                  # postgres + redis в докере
make db-migrate                          # применить схему
(cd apps/web && pnpm install && pnpm dev)
(cd services/api && pip install -e ".[dev]" && uvicorn app.main:app --reload)
```

Подробности, решения и архитектура — в [`docs/`](./docs) и [`CLAUDE.md`](./CLAUDE.md).

## Структура

```
apps/web/            фронт (Next.js + Flowbite + i18n)
services/api/        AI/скрапинг-пайплайн (FastAPI)
supabase/migrations/ схема БД + RLS
docs/                продуктовые и технические документы
```

## Документация

- [Обзор и decision log](./docs/00_README.md)
- [Рыночный ресёрч](./docs/01_market_research.md)
- [PRD](./docs/02_PRD.md)
- [Архитектура](./docs/03_architecture.md)
- [MVP-спека](./docs/04_mvp_spec.md)
- [AI-пайплайн и промпты](./docs/05_ai_pipeline_prompts.md)
- [Юнит-экономика](./docs/06_pricing_unit_economics.md)
