# HANDOFF

Что сделано в вехе M0, что нужно от владельца и как всё запустить. Ниже - актуальный статус, ключи, запуск и остатки онбординга (push в GitHub, Flowbite MCP).

## Статус M0 (каркас)

| Пункт | Статус | Детали |
|-------|--------|--------|
| Supabase: схема + RLS, изоляция тенантов | Готово | Локальный Supabase CLI стек. Найден и исправлен дефект схемы: рекурсия политики на `users` (`current_tenant_id()` переведён в `security definer`) и отсутствие табличных грантов supabase-ролям. Интеграционный тест доказывает, что тенант A не видит данные B. |
| Auth на web + защита роутов + создание тенанта | Готово | Supabase Auth (`@supabase/ssr`), связка middleware next-intl + сессия, страницы login/register/callback, защита `/[locale]/dashboard`, провижининг тенанта и owner-пользователя при регистрации. Тексты через next-intl (ru/en). |
| LLM-слой (instructor.from_litellm, metadata, ai_usage, Langfuse) | Готово, live-тест загейчен | Клиент считает стоимость и пишет в `ai_usage`, прокидывает `metadata{tenant_id, stage, user_id}`, трейс через success-callback в Langfuse. LiteLLM proxy и Langfuse v2 подняты в docker-compose. Реальный вызов LLM включается ключом (см. ниже). |
| БД-слой api (SQLAlchemy под 0001_init.sql, сессии service_role) | Готово | ORM-модели всех 9 таблиц, движок на psycopg3, сессия под ролью postgres (bypassrls) для пайплайна/админки. |
| .env + HANDOFF | Готово | `.env.example` обновлены, локальные `.env`/`.env.local` заведены (в git не попадают), этот файл. |

## Что нужно от владельца (ключи)

1. **LLM-провайдер** (минимум один, для скоринга достаточно Gemini):
   - `GEMINI_API_KEY` - стадия score (`gemini-2.0-flash-lite`),
   - `OPENAI_API_KEY` - стадия draft (`gpt-5-mini`), понадобится в M3,
   - `ANTHROPIC_API_KEY` - опционально, премиум-драфтинг.
   Класть в `services/api/.env` (для api) и в корневой `.env` (для LiteLLM proxy в docker-compose).
2. **Hosted Supabase** (когда переходим с локального стека на облако):
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` из дашборда проекта,
   - прогнать схему на облако: `DATABASE_URL=<hosted-db-url> make db-migrate`.
3. **Langfuse** - для локалки не нужен, бутстрапится docker-compose. Для облачного Langfuse дать `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST`.

Локальные `.env` уже заполнены значениями Supabase CLI (демо-ключи, публичные). Останется дописать только `GEMINI_API_KEY`.

## Как запустить локально

Предпосылки: Node 22+ (pnpm через corepack), Python 3.12+, Docker, Supabase CLI (`brew install supabase/tap/supabase`).

```bash
make up            # supabase start (Postgres+Auth :54321/:54322) + docker compose (redis, litellm, langfuse)
make db-reset      # применить миграции из supabase/migrations к локальному Supabase
make install       # зависимости web + api

# dev-серверы
make web           # фронт :3000
make api           # api  :8000
```

Порты: Supabase API :54321, Postgres :54322, LiteLLM proxy :4000, Langfuse :3001, Redis :6379.

## Тесты

```bash
make lint                 # web (eslint) + api (ruff) — как в CI
make test                 # unit-слой, без БД и ключей провайдеров (зелёный в CI)
make test-integration     # RUN_DB_TESTS=1: RLS-изоляция + БД-слой (нужен запущенный Supabase)

# реальный скоринг через LLM (нужен ключ провайдера):
cd services/api && . .venv/bin/activate
RUN_DB_TESTS=1 RUN_LIVE_LLM=1 GEMINI_API_KEY=... LANGFUSE_ENABLED=true pytest -q -m live
```

После live-теста скоринг тестовой статьи вернёт валидный `RelevanceScore`, строка появится в `ai_usage`, трейс - в Langfuse UI (http://localhost:3001).

## Осознанные отклонения от исходного каркаса

- **Локальный Postgres переехал в Supabase CLI.** Миграция использует `auth.uid()` и роли `authenticated`/`service_role`, которых нет в голом Postgres из docker-compose. Поэтому БД+Auth локально даёт `supabase start`, а docker-compose держит только вспомогательные сервисы (redis, litellm, langfuse).
- **В `supabase/config.toml` выключены тяжёлые локальные сервисы** (analytics/logflare, studio, storage, realtime, edge_runtime): их health-флап ронял `supabase start`. Для M0 нужны db + auth + rest + kong. Включить обратно при необходимости.
- **Фикс схемы 0001_init.sql:** `current_tenant_id()` стал `security definer` (иначе рекурсия политики на `users`), добавлены гранты `authenticated`/`service_role` на таблицы (без них RLS даёт "permission denied" ещё до проверки строк).

## Остаток онбординга

### Push в GitHub (из терминала с твоим git-auth)

Репозиторий: `https://github.com/ipolotsky/kate-searches`. Ветку M0 запушить и открыть PR по обычному флоу. Если остались stale-локи от Cowork:

```bash
rm -f .git/*.lock .git/**/*.lock
```

### Flowbite MCP

Скопировать `docs/mcp.example.json` → `.mcp.json` в корень и подставить команду запуска MCP-сервера внутри контейнера `flowbite-mcp-pro-100`. Claude Code подхватит сервер при следующем старте.

## Что дальше (M1)

Ingestion: RSS + sitemap + Crawl4AI адаптеры, extract + dedup + novelty, постановка задач в Celery. См. `docs/04_mvp_spec.md` §7.

## Ждём от Kate

Примеры её реальных статей с указанием инфоповода-источника - few-shot для брендового голоса (стадия генерации).
