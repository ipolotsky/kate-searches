# CLAUDE.md — контекст проекта KateSearches

> Этот файл читает Claude Code при старте в репозитории. Здесь — что за проект, какие решения приняты, как устроен код и как его запускать. Подробные продуктовые/технические доки — в `docs/`.

## TL;DR что это

B2B SaaS: ежедневно мониторит источники новостей в нише клиента → **скорит** каждую новость по кастомным критериям релевантности его аудитории → для прошедших отбор **генерит черновик SEO/AEO-поста** в голосе бренда, связывая новость как инфоповод с брендом клиента в статью-симбиоз → отдаёт в дашборд черновиков. Первый клиент — **LOOTON** (ресейл-маркетплейс премиум-одежды). Его доки уже задали спеку движков отбора и экстракции (см. `docs/05_ai_pipeline_prompts.md`).

## Зафиксированные решения (не пересматривать без явного запроса)

- **Стек:** Next.js 15 (App Router) + Flowbite React (фронт) + FastAPI (AI/скрапинг-пайплайн). Два сервиса, чёткая граница.
- **БД/Auth:** Supabase (Postgres + Auth + RLS). Изоляция тенантов — через RLS на уровне БД.
- **AI:** plain SDK + Instructor + Pydantic (без LangChain — DAG линейный). Гейтвей — LiteLLM (бюджеты per-tenant), метеринг — Langfuse.
- **i18n:** мультиязычность с первого дня (ru + en), расширяемо. Фронт — `next-intl`.
- **Юрисдикция:** глобально / не-РФ → Stripe + прямой доступ к OpenAI/Anthropic/Gemini.
- **Биллинг:** в MVP НЕТ, только cost-metering. Stripe — фаза 1.5. Поля plan/usage в схеме есть с D1.
- **Экспорт постов:** HTML / Markdown / copy-as-text (через редактор). Автопубликация в CMS — роадмап.
- **Генерация:** черновик — симбиоз «инфоповод × бренд». Новость органично связывается с брендом через его профиль (позиционирование, экспертиза, угол). Каталога товаров / продуктового слоя нет — связка идёт с брендом, не с SKU.
- **Источники в MVP:** RSS + news-sitemap + Crawl4AI-скрапер (Firecrawl fallback). Соцсети (Telegram/Reddit) — фаза 2, но адаптер-абстракция готова с D1.

Полный decision log — `docs/00_README.md`. Конкуренты/рынок — `docs/01_market_research.md`. Продукт — `docs/02_PRD.md`. Архитектура — `docs/03_architecture.md`. MVP-скоуп — `docs/04_mvp_spec.md`. Промпт-спеки — `docs/05_ai_pipeline_prompts.md`. Экономика — `docs/06_pricing_unit_economics.md`. Деплой/инфра — `docs/08_deployment.md`.

## Структура монорепы

```
kate-searches/
├── apps/web/            # Next.js 15 + Flowbite + next-intl (ru/en)
├── services/api/        # FastAPI: adapters → pipeline (extract/score/generate) → metering
├── supabase/migrations/ # SQL-схема + RLS
├── docs/                # продуктовые и технические доки (источник истины по продукту)
├── .github/workflows/   # ci.yml (lint+test, reusable) + deploy-staging/deploy-prod (docker rollout)
├── deploy/              # VM-стек: compose.yml, deploy.sh, traefik/, env.example (см. docs/08)
├── docker-compose.yml   # локальные postgres + redis
├── Makefile             # частые команды
└── CLAUDE.md            # этот файл
```

## Как запустить локально

Предпосылки: Node 22 (`.nvmrc`), pnpm, Python 3.12+, Docker (для локальных postgres/redis).

```bash
# 1. поднять инфру (postgres + redis)
make up                      # = docker compose up -d

# 2. фронт
cd apps/web && pnpm install && cp .env.example .env.local && pnpm dev

# 3. api
cd services/api && python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]" && cp .env.example .env && uvicorn app.main:app --reload

# применить миграции к локальной БД
make db-migrate             # psql < supabase/migrations/*.sql (или supabase db push)
```

Все ключи (LLM, Supabase) — в `.env` (см. `.env.example`). В git их НЕ коммитим.

## Команды (Makefile)

- `make up` / `make down` — docker инфра.
- `make web` / `make api` — dev-серверы.
- `make lint` / `make test` — линты и тесты обоих сервисов (как в CI).
- `make db-migrate` — применить миграции.

## Соглашения по коду

- **web:** TypeScript strict, ESLint + Prettier, компоненты Flowbite React, тексты только через `next-intl` (никаких хардкод-строк в JSX — всё в `messages/{ru,en}.json`). Тесты — Vitest.
- **api:** Python 3.12, типы обязательны, Ruff (lint+format), Pydantic v2 для всех схем, структурированный вывод LLM только через Instructor. Тесты — pytest.
- **БД:** любая таблица с `tenant_id` + RLS-политика. Миграции — только через файлы в `supabase/migrations/` (никаких ручных правок прод-схемы).
- **LLM:** все вызовы через `app/llm/client.py` (обёртка над LiteLLM) → трейс в Langfuse с тегами `tenant_id/user_id/stage`. Роутинг: score → дешёвая модель, generate → сильная.
- **Коммиты:** Conventional Commits (`feat:`, `fix:`, `chore:`...).

## Что НЕ делать в MVP

LangChain/LangGraph, Airbyte/Kafka, векторную БД, соцсеть-адаптеры (кроме абстракции), Stripe-биллинг, автопубликацию в CMS. Эти вещи в роадмапе — см. `docs/04_mvp_spec.md` §2.

## Известные внешние зависимости / TODO для владельца

- **GitHub push:** репо `https://github.com/ipolotsky/kate-searches`. Локальный коммит готов; запушить из Claude Code (`git push -u origin main`) — auth на машине владельца.
- **Flowbite MCP:** контейнер `flowbite-mcp-pro-100` поднят в докере, отдаёт MCP по streamable-HTTP на `http://localhost:3333/mcp` (health: `:3333/health`). Чтобы подключить в репо — скопировать `docs/mcp.example.json` → `.mcp.json` (HTTP-транспорт, готов). Пригодится на M4 (UI на Flowbite).
- **Пример CI/CD владельца:** `~/Develop/Mountly/TestTask` — свериться с их паттерном (lint+test отдельно от deploy; deploy всегда после прохождения тестов — уже отражено в `.github/workflows/`).
- **Ждём от Kate:** примеры её реальных статей с указанием инфоповода-источника (few-shot для брендового голоса).

## Ближайшие шаги (приоритет)

1. M0 — каркас: поднять web+api локально, Supabase-схема, LiteLLM+Langfuse.
2. M1 — ingestion: RSS+sitemap+Crawl4AI адаптеры, extract+dedup+novelty. Детальный план — `docs/07_m1_ingestion_plan.md`.
3. M2 — скоринг по rubric из `docs/05`.
4. M3 — генерация черновиков.
5. M4 — UI (дашборд/редактор/онбординг).
Подробнее — `docs/04_mvp_spec.md` §7.
