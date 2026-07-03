# HANDOFF

Актуальный снимок состояния после M0: что готово, что нужно от владельца, как запускать, как закоммитить и что делать дальше. Все изменения M0 лежат в рабочем дереве (ветка `m0/db-rls`), не закоммичены - коммитит владелец по playbook ниже.

## Статус M0 (каркас)

| Пункт | Статус | Детали |
|-------|--------|--------|
| Supabase: схема + RLS, изоляция тенантов | Готово | Локальный Supabase CLI стек. Исправлены два дефекта схемы: рекурсия политики на `users` (`current_tenant_id()` → `security definer`) и отсутствие табличных грантов supabase-ролям. По итогам верификации закрыта дыра внутри тенанта: `tenants`/`users`/`ai_usage` теперь read-only для `authenticated` (запись только под service_role), контент-таблицы редактируемы в своём тенанте. Интеграционные тесты доказывают меж-тенантную изоляцию и запрет эскалации. |
| Auth на web + защита роутов + создание тенанта | Готово | Supabase Auth (`@supabase/ssr`), связка middleware next-intl + сессия, страницы login/register/callback, защита `/[locale]/dashboard`, провижининг тенанта и owner-пользователя при регистрации с откатом при сбое и защитой от повторного email. Тексты через next-intl (ru/en). |
| LLM-слой (instructor.from_litellm, metadata, ai_usage, Langfuse) | Готово, live-тест загейчен | Клиент считает стоимость, пишет в `ai_usage`, прокидывает `metadata{tenant_id, stage, user_id}`, трейс через litellm success-callback в Langfuse (SDK закреплён на v2 под v2-сервер). LiteLLM proxy и Langfuse v2 подняты в docker-compose. Реальный вызов LLM включается ключом. |
| БД-слой api (SQLAlchemy под 0001_init.sql, сессии service_role) | Готово | ORM-модели всех 9 таблиц, движок на psycopg3, сессия под ролью postgres (bypassrls) для пайплайна/админки. |
| .env + HANDOFF | Готово | `.env.example` обновлены, локальные `.env`/`.env.local` заведены (в git не попадают), этот файл. |

## Что нужно от владельца (ключи)

1. **LLM-провайдер** (минимум один, для скоринга достаточно Gemini):
   - `GEMINI_API_KEY` - стадия score (`gemini-2.0-flash-lite`),
   - `OPENAI_API_KEY` - стадия draft (`gpt-5-mini`), понадобится в M3,
   - `ANTHROPIC_API_KEY` - опционально, премиум-драфтинг.
   Класть в `services/api/.env` (для api) и в корневой `.env` (для LiteLLM proxy).
2. **Hosted Supabase** (переход с локального стека на облако):
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` из дашборда,
   - прогнать схему: `DATABASE_URL=<hosted-db-url> make db-migrate` (миграция идемпотентна, повторный прогон безопасен).
3. **Langfuse** - для локалки не нужен, бутстрапится docker-compose. Для облачного Langfuse дать `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST`.

Локальные `.env` уже заполнены значениями Supabase CLI (демо-ключи, публичные). Останется дописать только `GEMINI_API_KEY`.

## Как запустить локально

Предпосылки: Node 22+ (pnpm через corepack), Python 3.12+, Docker, Supabase CLI (`brew install supabase/tap/supabase`).

```bash
make up            # supabase start (Postgres+Auth :54321/:54322) + docker compose (redis, litellm, langfuse)
make db-reset      # применить миграции из supabase/migrations к локальному Supabase
make install       # зависимости web + api

make web           # фронт :3000
make api           # api  :8000

make down          # остановить docker compose + supabase stop
```

Порты: Supabase API :54321, Postgres :54322, LiteLLM proxy :4000, Langfuse :3001, Redis :6379.

## Тесты и верификация

```bash
make lint                 # web (eslint) + api (ruff) — как в CI
make test                 # unit-слой, без БД и ключей (зелёный в CI)
make test-integration     # RUN_DB_TESTS=1: RLS-изоляция + control-tables read-only + БД-слой (нужен Supabase)

# реальный скоринг через LLM (нужен ключ провайдера):
cd services/api && . .venv/bin/activate
RUN_DB_TESTS=1 RUN_LIVE_LLM=1 GEMINI_API_KEY=... LANGFUSE_ENABLED=true pytest -q -m live
```

После live-теста скоринг тестовой статьи вернёт валидный `RelevanceScore`, строка появится в `ai_usage`, трейс - в Langfuse UI (http://localhost:3001).

## Коммит M0 (playbook)

Коммитит владелец. Порядок C1→C6, `.gitignore` намеренно исключён (в нём чужая правка про `settings.local.json`). Собиралось всё сразу, поэтому пара файлов несёт изменения нескольких подзадач - это отмечено; при желании их можно разнести через `git add -p`. Финальное дерево целиком зелёное.

```bash
# C1 — baseline + web lockfile
git add services/api/app/adapters/rss.py services/api/app/pipeline/dedup.py \
  services/api/tests/test_dedup.py apps/web/next-env.d.ts apps/web/package.json \
  pnpm-lock.yaml .github/workflows/ci.yml
git commit -m "chore: fix ruff violations, url scheme canonicalization, add web lockfile"

# C2 — Supabase CLI + RLS (рекурсия/гранты/read-only control-таблицы) + изоляционный тест
git add supabase/migrations/0001_init.sql supabase/config.toml supabase/.gitignore \
  Makefile services/api/pyproject.toml services/api/tests/conftest.py \
  services/api/tests/integration/__init__.py services/api/tests/integration/test_rls.py
git commit -m "feat(db): supabase CLI local stack, fix RLS recursion and grants, add RLS isolation test"

# C3 — БД-слой api (config.py несёт db-default + llm-настройки)
git add services/api/app/db services/api/app/config.py \
  services/api/tests/test_db_models.py services/api/tests/integration/test_db_layer.py
git commit -m "feat(api): SQLAlchemy models and service_role session for schema 0001"

# C4 — LLM-слой + инфра (docker-compose несёт и удаление postgres, и litellm/langfuse)
git add services/api/app/llm/client.py infra/litellm/config.yaml docker-compose.yml \
  services/api/tests/test_llm_client.py services/api/tests/integration/test_llm_live.py
git commit -m "feat(llm): working structured completion with ai_usage metering, LiteLLM+Langfuse infra"

# C5 — Web Supabase Auth
git add apps/web/src/lib apps/web/src/middleware.ts "apps/web/src/app/[locale]/auth" \
  "apps/web/src/app/[locale]/login" "apps/web/src/app/[locale]/register" \
  apps/web/src/components/auth "apps/web/src/app/[locale]/dashboard/page.tsx" \
  apps/web/messages/en.json apps/web/messages/ru.json
git commit -m "feat(web): supabase auth, protected routes, tenant provisioning, i18n"

# C6 — env + HANDOFF
git add .env.example services/api/.env.example apps/web/.env.example docs/HANDOFF.md
git commit -m "docs: env examples and M0 handoff"
```

Push и PR - обычным флоу (репо `https://github.com/ipolotsky/kate-searches`). Если снова застрянет `.git/index.lock` (пустой файл, git-процессов нет): `rm -f .git/index.lock`.

## Осознанные отклонения от исходного каркаса

- **Локальный Postgres переехал в Supabase CLI.** Миграция использует `auth.uid()` и роли `authenticated`/`service_role`, которых нет в голом Postgres. БД+Auth локально даёт `supabase start`, docker-compose держит только redis + litellm + langfuse.
- **В `supabase/config.toml` выключены тяжёлые локальные сервисы** (analytics/logflare, studio, storage, realtime, edge_runtime): их health-флап ронял `supabase start`. Для M0 нужны db + auth + rest + kong. Включить обратно при необходимости.
- **Фикс схемы 0001_init.sql:** `current_tenant_id()` → `security definer`; гранты supabase-ролям; `tenants`/`users`/`ai_usage` read-only для `authenticated`.

## Известные хвосты (follow-ups, не блокеры)

- **Дефолт-привилегии в миграции.** `alter default privileges ... grant ... update, delete ... to authenticated` даёт будущим таблицам (M1+) полный CRUD для `authenticated`. Сейчас дыры нет, но любая новая control-таблица (billing, audit) окажется писабельной участником, если забыть `revoke`. Рекомендация: сменить дефолт на `grant select`, а запись выдавать явным грантом per-table. Решение отложено под M1 (меняет посадку миграций).
- **register при confirmations=ON** редиректит на `/dashboard`, откуда middleware вернёт на login (UX, не безопасность; локально confirmations=OFF, поток гладкий).
- **matcher middleware** пропускает пути с точкой (`/dashboard/report.v2`) - в M0 защищённых суб-роутов с точками нет.
- **PostCard.tsx + namespace `post.*`** стали мёртвым кодом после переписи дашборда (вернутся в M4).
- **Конвенц-нить**: деструктуризация params в page-файлах (идиома Next), порядок helper-функций, инлайн-комменты. Косметика.

## Остаток онбординга

- **Flowbite MCP:** скопировать `docs/mcp.example.json` → `.mcp.json` и подставить команду запуска MCP внутри контейнера `flowbite-mcp-pro-100`.

## Что дальше (M1)

Ingestion: RSS + sitemap + Crawl4AI адаптеры, extract + dedup + novelty, постановка задач в Celery. Точки входа уже есть: `services/api/app/adapters/` (RSS реализован, остальные - TODO), `app/pipeline/dedup.py` (канонизация + свежесть), эндпоинт `POST /internal/pipeline/run` (заглушка). См. `docs/04_mvp_spec.md` §7.

## Ждём от Kate

Примеры её реальных статей с указанием инфоповода-источника - few-shot для брендового голоса (стадия генерации).
