# HANDOFF

Актуальный снимок состояния после M0 и M1: что готово, что нужно от владельца, как запускать, как закоммитить и что делать дальше. Статус M1 (ingestion) и починенные по итогам ревью баги — в разделе «Статус M1» ниже. Изменения M1 лежат в рабочем дереве, не закоммичены.

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

- **Flowbite MCP:** контейнер `flowbite-mcp-pro-100` поднят в докере, слушает streamable-HTTP на `http://localhost:3333/mcp` (health: `:3333/health`, serverInfo `flowbite-mcp`). Чтобы подключить в репо — скопировать `docs/mcp.example.json` → `.mcp.json` (HTTP-транспорт уже прописан, команду подставлять не нужно). `.mcp.json` в git не коммитим. Реально пригодится на M4 (UI на Flowbite).

## Продуктовая корректировка: убраны товары (после M0, до M1)

Продуктовая рамка уточнена: черновик — симбиоз «инфоповод × бренд». Новость органично связывается с брендом через его профиль (позиционирование, экспертиза, угол), без каталога товаров. Продуктового слоя (SKU) в продукте больше нет. Правки затронули часть файлов из M0-плейбука выше, при коммите учитывать:

- **Схема (`supabase/migrations/0001_init.sql`):** удалена таблица `products` (+ индексы), удалён `posts.linked_products`, `products` убран из RLS-массивов. Схема ещё не в проде (локальный Supabase) - правим 0001 на месте, отдельная миграция не нужна.
- **api-код:** удалены ORM `Product` (`app/db/models.py`, `app/db/__init__.py`) и `posts.linked_products`; из `test_db_models.py` убран `products`; в `app/models/drafts.py` убраны `LinkedProduct`/`linked_products`, добавлено поле `brand_tie_in` (угол симбиоза); `app/pipeline/generation.py` переписан под «инфоповод × бренд», убран параметр `products`; в `scoring.py` мелкая правка формулировки. Ruff + `test_db_models` зелёные.
- **Доки:** `CLAUDE.md`, `README.md`, `docs/00`-`06`, `docs/mcp.example.json` перепаны под новую рамку; поправлен роадмап M3 и открытые вопросы PRD §10 (вопрос про каталог товаров снят).
- **brand_tie_in** персистится в существующем `posts.seo` (jsonb), отдельная колонка не нужна.

## Статус M1 (ingestion) — готово

Веха M1 реализована целиком по плану `docs/07_m1_ingestion_plan.md` (все 15 задач T1-T15). Полный вертикальный срез `fetch -> normalize -> novelty -> persist -> extract -> dedup` работает, AC-1 доказан интеграционным тестом на реальном Supabase.

Что сделано:
- **Контракт адаптера** (`app/adapters/base.py`, `cursors.py`, `registry.py`): `SourceAdapter` Protocol с декларативными `AdapterCapabilities`/`config_model`, типизированные курсоры (ETag/Timestamp/SinceId/Page), `AdapterRegistry` с `register`/`describe()` (готовое API для M4-формы источника). `Document.body_is_complete`.
- **Адаптеры**: RSS (мигрирован, dateless-гейт), sitemap (news-sitemap + sitemap-index), scraper (через `CascadeFetcher`). Все в реестре.
- **Fetch-слой** (`app/fetch/`): `HttpxFetcher -> Crawl4aiFetcher (extra [scraper]) -> FirecrawlFetcher`, `CascadeFetcher` эскалирует по качеству; `worker/throttle.py` (Redis token-bucket per host), `worker/robots.py` (robots-кэш с TTL, fail-open политика).
- **Extract** (`app/pipeline/extract.py`): гидратация тела через каскад + trafilatura, пересчёт `content_hash`/`simhash`, `new -> extracted`, учёт COGS платного скрапинга в `ai_usage(stage='extract')`.
- **Дедуп и новизна** (`app/pipeline/dedup.py`): tz-aware `is_novel` (граница по таймзоне тенанта, backfill по `since`, dateless не проходит), `simhash64`/`hamming` со знаковым bigint-маппингом, кластерный дедуп (content-hash exact + simhash near-dup) с кросс-источниковым priority-тай-брейком.
- **Персистентность** (`app/db/repositories.py`, миграция `0002_ingestion.sql`): `ArticleRepository`/`SourceRepository`/`PipelineRunRepository`, upsert `ON CONFLICT DO NOTHING`, провенанс `article_sources`, леджер `pipeline_runs`, `source_secrets` (DDL-шов). ORM синхронизирован 1:1.
- **Оркестрация** (`app/worker/`): Celery-app с result backend (нужен для chord-барьера), топология `dispatch_due_tenants (tz) -> run_tenant_pipeline -> chord(ingest) -> finalize_fetch -> chord(extract) -> dedup_and_finalize`. Синхронный `run_tenant_pipeline_sync` — детерминированный барьер для тестов и ручного прогона.
- **Эндпоинты** (`app/api/routes.py`): `POST /internal/pipeline/run` (claim + enqueue), `POST /internal/sources/test` (синхронный dry-run с sample/is_novel/warnings, без записи в БД и без платного fetch).
- **Инфра**: `services/api/Dockerfile`, сервисы `worker`/`beat` в `docker-compose.yml`, make-таргеты `worker`/`beat`, extra `[scraper]` (crawl4ai/playwright не тянется в `make test`).

### Независимый ревью и починенные баги

После реализации прогнан независимый multi-agent adversarial review (4 измерения, верификация каждой находки). Подтверждено и починено 8 дефектов (все с регресс-тестами):
1. **Зависание прогона (high)**: header-задача chord (`ingest_source`/`extract_article`) при исключении завершалась в FAILURE, из-за чего Celery пропускал body (`finalize_fetch`/`dedup_and_finalize`) и `pipeline_runs` навсегда висел в `running`, а статьи других источников не обрабатывались. Теперь header-задачи никогда не падают в FAILURE (transient ретраятся, остальное -> failed-sentinel), partial-run гарантирован. То же в sync-пути.
2. **Утечка COGS (high)**: scraper-адаптер включал платный Firecrawl внутри `fetch`, и стоимость терялась мимо `ai_usage`. Теперь `allow_paid=False` в адаптере, платную эскалацию с учётом делает extract.
3. **Дедуп-цепочки (correctness)**: попарный дедуп мог оставить `duplicate_of`, указывающий на строку, которая сама стала дублем, и обрабатывал лишь один near-dup за проход. Переписан на кластерную модель: единственный канон, все проигравшие линкуются прямо на него.
4. **robots 5xx (correctness)**: серверная ошибка robots.txt парсилась как правила (HTML-тело), выдавая allow-all. Теперь 5xx/недоступность идёт по fail-open политике без парсинга тела.
5. **DST-пропуск диспатчера (medium)**: строгое равенство локального часа теряло прогон в день spring-forward. Теперь `>=` час прогона + catch-up зависших `running`-прогонов в `dispatch_due_tenants`.
6. **Потеря записей sitemap (medium)**: усечение по `max_urls` в document-order двигало курсор мимо невыбранных новых записей. Теперь сортировка по дате ASC — невыбранные дочитываются в следующих прогонах.
7. **Троттлинг между хостами (low)**: общий Redis token-bucket использовал `time.monotonic` (несопоставим между процессами). Теперь wall-clock `time.time`.
8. **TRUNCATE-дыра (security, defense-in-depth)**: `authenticated` имел `TRUNCATE` на control- и content-таблицах (обходит RLS, сносит данные всех тенантов). Закрыто в `0002` для всех таблиц. Дыра на control-таблицах M0 (`tenants`/`users`/`ai_usage`) тоже была реальной и закрыта.

Отклонены как невоспроизводимые/по-дизайну: демоут `scored`/`drafted` (заморозка каноничности работает), таймаут `/sources/test` (не воспроизводится).

### Проверка M1

```bash
make lint                 # ruff чисто
make test                 # 77 unit зелёных (без БД/ключей/playwright)
make test-integration     # 11 integration: AC-1, RLS control-таблиц, дедуп-кластер, partial-run
```

Миграция `0002` идемпотентна (повторный прогон без ошибок). `worker`/`beat` стартуют в docker-compose.

### Хвосты M1 (follow-ups, не блокеры)

- `TransientFetchError`/`PermanentFetchError` — контракт ретраев готов, но адаптеры пока деградируют в warnings, а не поднимают их. Первый адаптер с ретраебельными сетевыми ошибками должен поднимать `TransientFetchError`.
- Commit-before-enqueue: полностью снимается только транзакционным outbox; сейчас смягчено catch-up-логикой диспатчера (перезапуск зависших `running`-прогонов через `pipeline_run_stale_minutes=30`).
- Пороги (тонкое тело 500, Hamming <= 3, стоимость Firecrawl-вызова) вынесены в `settings`, калибровать на реальных источниках LOOTON в M6.

## Что дальше (M2)

Скоринг по rubric из `docs/05_ai_pipeline_prompts.md`. Точка прицепа готова: `score_article` вешается group-ом на post-extract барьер `dedup_and_finalize` с гейтом `status='extracted'`; дедуп по контенту уже прошёл, M2 не платит LLM за дубли; `ai_usage(stage='score', pipeline_run_id)` готов. См. `docs/04_mvp_spec.md` §7.

## Ждём от Kate

Примеры её реальных статей с указанием инфоповода-источника - few-shot для брендового голоса (стадия генерации).
