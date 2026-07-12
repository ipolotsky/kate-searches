# HANDOFF

Актуальный снимок состояния: что готово, что развёрнуто, что нужно от владельца, как запускать. Инженерный лог вех M0-M6.4 — ниже; текущий статус прода — в разделе сразу под этим.

Состояние git: все вехи M0-M6.4 закоммичены и запушены в `main`. Плейбуки коммитов ниже — исторический след, повторно не выполнять.

## Актуальный статус: прод и stage развёрнуты (обновлено 2026-07-12)

Прод и stage работают на одной VM (GCP, Debian 13, `35.223.85.130`) под CI/CD. Полный спек инфраструктуры и гочи запуска — `docs/08_deployment.md`.

**Окружения (оба live, TLS Let's Encrypt, все контейнеры healthy):**
- Прод — https://taskyou.me, Supabase-проект `bkwyqfqytisnrdxfieha`.
- Stage — https://stage.taskyou.me, отдельный Supabase-проект `yzoqhvqdvyscfaclxyde`.

**CI/CD:** PR → деплой на stage (бот постит ссылку + чек-лист в PR); merge в `main` → деплой на прод. Образы собираются в GHCR, VM катит через `docker rollout` (zero-downtime, проверено 195/195 запросов без сбоя). Изоляция — два compose-проекта `kate-prod`/`kate-stage` (свои сети, Redis, `.env`); у stage лимиты памяти и concurrency воркера ниже. Миграции 0001-0009 накатывает job `migrate` идемпотентно и fail-fast на каждый деплой.

**Секреты:** рантайм (service_role, ключи LLM, `DATABASE_URL`) — только в `/srv/kate-searches/{prod,stage}/.env` (chmod 600), в CI их нет. Билд-тайм (`NEXT_PUBLIC_*`) и деплойные (`VPS_*`, `*_DATABASE_URL` для миграций) — в GitHub Secrets. CI ходит на VM выделенным ssh-ключом.

**Ключи LLM (проверено на VM):** `GEMINI_API_KEY` (score) и `OPENAI_API_KEY` (draft) проставлены на обоих окружениях — полный пайплайн может гонять. `ANTHROPIC_API_KEY` пуст (опционально).

**Email (M6.3) — включён:** Resend, домен `taskyou.me` верифицирован, отправка подтверждена тестовым письмом. Оба окружения шлют с `no-reply@taskyou.me`. Auth-письма Supabase (confirm/reset/magic-link) переведены на Resend через Custom SMTP + Site URL/Redirect на домены — настроено владельцем. `RESEND_WEBHOOK_SECRET` пуст (нужен только для трекинга доставок/отписок, на отправку не влияет).

**Ещё не сделано (осознанно):**
- **Stripe (M6.2):** ключи пусты, биллинг выключен. Флип test→live — перед публичной рекламой (замена `STRIPE_*` секретов + вебхук `https://taskyou.me/api/stripe/webhook`).
- **Сид пилота LOOTON:** после регистрации тенанта — `make seed-looton DB=<prod_url> ARGS="--owner-email kate@..."`.
- **Трат LLM пока нет:** 0 тенантов → beat ничего не диспатчит (проверено: `ai_usage=0` в обеих БД).

## Статус M0 (каркас)

| Пункт | Статус | Детали |
|-------|--------|--------|
| Supabase: схема + RLS, изоляция тенантов | Готово | Локальный Supabase CLI стек. Исправлены два дефекта схемы: рекурсия политики на `users` (`current_tenant_id()` → `security definer`) и отсутствие табличных грантов supabase-ролям. По итогам верификации закрыта дыра внутри тенанта: `tenants`/`users`/`ai_usage` теперь read-only для `authenticated` (запись только под service_role), контент-таблицы редактируемы в своём тенанте. Интеграционные тесты доказывают меж-тенантную изоляцию и запрет эскалации. |
| Auth на web + защита роутов + создание тенанта | Готово | Supabase Auth (`@supabase/ssr`), связка middleware next-intl + сессия, страницы login/register/callback, защита `/[locale]/dashboard`, провижининг тенанта и owner-пользователя при регистрации с откатом при сбое и защитой от повторного email. Тексты через next-intl (ru/en). |
| LLM-слой (instructor.from_litellm, metadata, ai_usage, Langfuse) | Готово, live-тест загейчен | Клиент считает стоимость, пишет в `ai_usage`, прокидывает `metadata{tenant_id, stage, user_id}`, трейс через litellm success-callback в Langfuse (SDK закреплён на v2 под v2-сервер). LiteLLM proxy и Langfuse v2 подняты в docker-compose. Реальный вызов LLM включается ключом. |
| БД-слой api (SQLAlchemy под 0001_init.sql, сессии service_role) | Готово | ORM-модели всех 9 таблиц, движок на psycopg3, сессия под ролью postgres (bypassrls) для пайплайна/админки. |
| .env + HANDOFF | Готово | `.env.example` обновлены, локальные `.env`/`.env.local` заведены (в git не попадают), этот файл. |

## Что нужно от владельца (ключи)

> Исторический M0-контекст. Hosted Supabase, ключи провайдеров и деплой уже сделаны — актуальное состояние в разделе «Актуальный статус» выше.

Важно про два `.env`: api читает СВОЙ `services/api/.env` (при `LITELLM_BASE_URL=""` вызовы идут напрямую в SDK провайдера). Корневой `.env` читает docker-compose (LiteLLM proxy). Плюс: `llm/client.py` теперь бриджит ключи провайдера из `settings` в `os.environ` (`_configure_provider_keys`), потому что litellm читает ключи из окружения, а pydantic-settings их туда не экспортирует. Итог: достаточно положить ключ в `services/api/.env` — прямые вызовы его подхватят.

Текущее состояние ключей (проверено):
- `GEMINI_API_KEY` - ПРОСТАВЛЕН в `services/api/.env` и корневом `.env`. Стадия score M2 (`gemini-2.0-flash-lite`). LLM-цепочка проверена live-вызовом: запрос доходит до Gemini с валидной авторизацией (упирается только в per-minute квоту free-tier - транзиентный лимит, не проблема конфигурации; на платном тарифе/с паузой между вызовами проходит зелёным).
- `OPENAI_API_KEY` - проставлен в `services/api/.env` и корневом `.env`. Стадия draft M3 (`gpt-5-mini`).
- `ANTHROPIC_API_KEY` - опционально, премиум-драфтинг M3.
- `FIRECRAWL_API_KEY` - опционально, платный fallback скрапинга (extract эскалирует на него при тонком теле; учёт стоимости в `ai_usage` уже готов).

Прочее от владельца:
1. **Hosted Supabase** (переход с локального стека на облако): `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` из дашборда; прогнать схему `DATABASE_URL=<hosted-db-url> make db-migrate` (миграции 0001+0002 идемпотентны, повторный прогон безопасен).
2. **Langfuse** - для локалки не нужен, бутстрапится docker-compose. Для облачного дать `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST`.

Локальные `.env` заполнены значениями Supabase CLI (демо-ключи, публичные), `DATABASE_URL`/`REDIS_URL`/`GEMINI_API_KEY`/`OPENAI_API_KEY` проставлены. Со стороны ключей для M2 всё готово - остаётся только реализация скоринга (см. раздел «Что дальше (M2)»).

## Как запустить локально

Предпосылки: Node 22+ (pnpm через corepack), Python 3.12+, Docker, Supabase CLI (`brew install supabase/tap/supabase`).

```bash
make up            # supabase start (Postgres+Auth :54321/:54322) + docker compose (redis, litellm, langfuse)
make db-reset      # применить миграции из supabase/migrations к локальному Supabase
make install       # зависимости web + api

make web           # фронт :3000
make api           # api  :8000
make worker        # Celery worker (ingestion: очереди default/fetch/extract) — нужен Redis
make beat          # Celery beat (tz-диспетчер дневных прогонов)

make down          # остановить docker compose + supabase stop
```

Порты: Supabase API :54321, Postgres :54322, LiteLLM proxy :4000, Langfuse :3001, Redis :6379.

Для ingestion-пайплайна (M1) нужны поднятый Redis (брокер+бэкенд Celery, стор троттлинга/robots) и запущенный `worker`. `beat` планирует дневные прогоны по таймзоне тенанта; для ручного прогона есть `POST /internal/pipeline/run`. Локально Redis поднят через `docker compose up -d redis` (входит в `make up`).

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

- **Дефолт-привилегии в миграции (частично закрыто в M1).** В M1 ревью выяснилось, что Supabase дефолтно грантит `authenticated` ВСЕ привилегии на новые таблицы, включая `TRUNCATE` (обходит RLS). В `0002` явно `revoke` для всех control- и content-таблиц (M0 и M1), это покрыто integration-тестом RLS. Остаётся дисциплина: любая НОВАЯ control-таблица (billing, audit) в будущих миграциях требует явного `revoke insert/update/delete/truncate`, иначе окажется писабельной участником. Радикальный вариант (сменить `alter default privileges` на `grant select`) не делали, чтобы не менять посадку 0001; держать per-table revoke конвенцией.
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

Всего 88 passed, 1 skipped (live-LLM, нужен ключ). Миграция `0002` идемпотентна (повторный прогон без ошибок).

Помимо тестов прогнан живой E2E на реальной инфре (не моки): поднят Redis, запущен настоящий Celery worker, прогон поставлен через `.delay`. Проверено, что реальный chord-барьер срабатывает - в логе воркера `run_tenant_pipeline -> ingest_source -> finalize_fetch -> extract_article ×3 -> dedup_and_finalize` (все extract завершились ДО dedup), прогон финализирован в `success` с корректным контент-дедупом и провенансом. `RateLimiter`/`RobotsPolicy` отдельно проверены против живого Redis. `worker`/`beat` стартуют в docker-compose.

### Хвосты M1 (follow-ups, не блокеры)

- `TransientFetchError`/`PermanentFetchError` — контракт ретраев готов, но адаптеры пока деградируют в warnings, а не поднимают их. Первый адаптер с ретраебельными сетевыми ошибками должен поднимать `TransientFetchError`.
- Commit-before-enqueue: полностью снимается только транзакционным outbox; сейчас смягчено catch-up-логикой диспатчера (перезапуск зависших `running`-прогонов через `pipeline_run_stale_minutes=30`).
- Пороги (тонкое тело 500, Hamming <= 3, стоимость Firecrawl-вызова) вынесены в `settings`, калибровать на реальных источниках LOOTON в M6.

### Коммит M1

Закоммичен и запушен одним коммитом `e3b080a` (весь ingestion + фиксы после ревью). Отдельного плейбука не требуется. Единственная незакоммиченная правка сейчас - актуализация этого HANDOFF.

## Статус M2 (скоринг) — готово

Веха M2 реализована как wiring готового движка в DAG. Полный срез `extract -> dedup -> score -> finalize` работает, доказан integration-тестом на реальном Supabase.

Что сделано:
- **Стадия** (`app/pipeline/scoring.py`): `score_article_run(session, article_id, run_id)` - грузит статью + `brand_profile` тенанта, собирает profile-dict (`company_name` из `tenants.name` + поля профиля), вызывает `score_article`, пишет `relevance`/`relevance_score`, guard-переход `extracted -> scored|filtered_out`. Гейт отбора: `passes_threshold AND overall_score >= brand_profiles.score_threshold`. Веса `brand_profiles.criteria_weights` инжектятся в system-промпт. `build_messages`/`score_article` типизированы через `ScorableDocument` Protocol (принимают и `Document`, и ORM `Article`), guard на пустой `published_at`.
- **Репозиторий** (`app/db/repositories.py`): `BrandProfileRepository.get_by_tenant`, `ArticleRepository.advance_scored` (guard `WHERE status='extracted'`, идемпотентно), `run_counters` считает `scored`/`filtered_out`.
- **Атрибуция стоимости** (`app/llm/client.py`): `structured_completion(..., pipeline_run_id=...)` прокидывает run в `ai_usage` (раньше писался `None`).
- **Оркестрация** (`app/worker/tasks.py`): терминал `dedup_and_finalize` разбит на `dedup_and_score` (дедуп -> `chord(group(score_article))(finalize_run)`) + `finalize_run`. `score_article` - header-задача (sentinel-возврат, transient LLM-ошибки ретраятся с backoff, не ронять chord). Sync-ядро `dedup_and_score_run` для тестов и ручного прогона.
- **Инфра**: новая очередь `score` (`celery_app.py` task_routes, `Makefile`/`docker-compose.yml` worker `-Q ...,score`). Миграция `0003_scoring.sql` (колонки `pipeline_runs.scored`/`filtered_out`, идемпотентна).
- **Схема** (без изменений контракта): `articles.relevance` (jsonb), `articles.relevance_score` (int), статусы `scored`/`filtered_out` уже были в check-констрейнте с M1; `RelevanceScore` (11 критериев + агрегаты) готов с M0.

### Проверка M2

```bash
make lint                 # ruff чисто
make test                 # 86 unit зелёных (мок LLM, без БД/ключей)
make test-integration     # RUN_DB_TESTS=1: 13 integration (AC-1 + скоринг: scored/filtered_out, счётчики)
```

Скоринг-integration (`tests/integration/test_scoring_run.py`) мокает `scoring.score_article` и через `run_tenant_pipeline_sync` доказывает переход `scored`/`filtered_out`, запись `relevance`/`relevance_score` и счётчики прогона. Юниты (`tests/test_scoring.py`) покрывают `build_messages` (веса/критерии) и решающую логику порога (таблица кейсов). Живой LLM - `tests/integration/test_llm_live.py` под `RUN_LIVE_LLM=1` + `GEMINI_API_KEY`.

### Хвосты M2 (follow-ups, не блокеры)

- **Веса критериев** идут только в промпт (LLM взвешивает сам). Детерминированный пересчёт `overall_score` из `criteria_weights` - роадмап; калибровать пороги/веса на реальном потоке LOOTON в M6.
- **История оценок**: `relevance`/`relevance_score` - один слот на статью (перезапись при повторном скоринге). Отдельная таблица истории/версий - если понадобится A/B весов.
- **ai_usage при повторе**: строка стоимости пишется в отдельной транзакции внутри `structured_completion`; если запись статьи упадёт после LLM-вызова, ретрай оплатит скоринг повторно (MVP-допущение).

## Статус M3 (генерация черновиков) — готово

Веха M3 реализована как wiring готового движка `app/pipeline/generation.py` в отдельный on-demand-поток. Полный срез `scored -> DraftPost -> posts` работает, доказан integration-тестом на реальном Supabase.

Ключевое продуктовое решение владельца: **генерация запускается по требованию, а не в дневном прогоне**. Сильная модель дороже скоринга в ~15-100×, поэтому дневной прогон как и раньше останавливается на `scored`, а черновики генерятся отдельным триггером (эндпоинт), где Kate курирует, какие статьи драфтить. Это НЕ ломает M1/M2: sync-ядро дневного прогона и score-chord не тронуты.

Что сделано:
- **Стадия** (`app/pipeline/generation.py`): `generate_draft_run(article_id)` - guard `status='scored'`, грузит `brand_profile`+`tenant`, реконструирует `RelevanceScore` из `articles.relevance`, выбирает язык (`brand_profiles.locales[0]` -> `tenant.default_locale` -> `article.language` -> `en`), зовёт `generate_draft` и пишет строку `posts`. Переход `scored -> drafting -> drafted` через промежуточный **claim-статус `drafting`**: атомарный claim (`UPDATE ... WHERE status='scored'`) ДО LLM-вызова не даёт конкурентным on-demand генерациям дублировать спенд сильной модели на одну статью; при сбое LLM claim откатывается (`drafting -> scored`). LLM-вызов вынесен между двумя короткими транзакциями (сильная модель держит ~20-60с - нельзя держать открытой write-tx). `GeneratableDocument` Protocol (принимает ORM `Article`), guard на `published_at=None`, форматтер few-shot `voice_examples` с капом 3.
- **Один язык на статью** (решение владельца): `brand_profiles.locales[0]`. Мультилокальность (пост на каждый locale) - роадмап, аддитивно (у `posts` нет unique на `article_id`).
- **Персист** (`app/db/repositories.py`): `PostRepository.create_from_draft` (маппинг `DraftPost -> posts`: `body_markdown`/`faq`/`json_ld`/`suggested_titles`; `seo = {meta_description, keywords, entities, brand_tie_in, seo_instructions}`; `ai_model`/`ai_cost_usd`), `ArticleRepository.claim_for_draft`/`advance_drafted`/`release_draft_claim` (guard-переходы claim-машины), `ArticleRepository.scored_articles`, `PipelineRunRepository.refresh_drafted` (точечный пересчёт счётчика `drafted` без ре-финализа прогона).
- **Стоимость per-post** (решение владельца - заполнять `posts.ai_cost_usd`): `app/llm/client.py` расширен аддитивно - `structured_completion_with_usage(...) -> (result, cost)`; `structured_completion` сведён к тонкой обёртке над ней (сигнатура и поведение для M2-скоринга неизменны). Стоимость пишется и в `posts.ai_cost_usd`, и в `ai_usage(stage='draft', pipeline_run_id=<прогон, что заскорил статью>)`.
- **Оркестрация** (`app/worker/tasks.py`): sync-ядро `run_tenant_generation_sync(tenant_id, article_ids=None)`; продакшен `run_tenant_generation -> chord(group(generate_article))(finalize_generation)`. `generate_article` - header-задача (не падает в FAILURE, transient LLM-ошибки ретраятся с backoff). `finalize_generation` обновляет `pipeline_runs.drafted` затронутых прогонов.
- **Эндпоинт** (`app/api/routes.py`): `POST /internal/pipeline/generate {tenant_id, article_ids?}` - claim кандидатов + enqueue (зеркало `/internal/pipeline/run`). По умолчанию весь `scored`-хвост, опц. фильтр `article_ids` для курируемой генерации из дашборда.
- **Инфра**: новая очередь `generate` (`celery_app.py` task_routes, `Makefile`/`docker-compose.yml` worker `-Q ...,score,generate`). Миграция `0004_generation.sql` (колонка `pipeline_runs.drafted` + claim-статус `'drafting'` в `articles.status` CHECK, идемпотентна). ORM `PipelineRun.drafted`.
- **Схема** (без изменений контракта посева): `posts` и его RLS есть с 0001, `'drafted'` в `articles.status` CHECK с 0002, `DraftPost` готов с M0.

Порог `llm_draft_max_tokens=16384` в `settings`: дефолтные 2048 обрезают `DraftPost`, а `gpt-5-mini` - reasoning-модель (reasoning-токены тоже идут в лимит), поэтому нужен запас, иначе `finish_reason='length'` -> `IncompleteOutputException` у Instructor (поймано живым E2E).

### Независимый ревью M3 и починенные баги

После реализации прогнан multi-agent adversarial review (4 линзы, верификация каждой находки). Подтверждено и починено 2 дефекта:
1. **Конкурентный double-spend (medium)**: у on-demand генерации не было claim-guard (в отличие от дневного прогона под `claim_run`). Два конкурентных триггера (двойной клик / повторный enqueue) звали сильную модель дважды на каждую scored-статью - guard `advance_drafted` резал дубль `posts`, но деньги уже потрачены. Починено промежуточным claim-статусом `drafting` (атомарный claim ДО LLM; проигравший не идёт в модель; откат при сбое).
2. **Escape в FAILURE на исчерпании ретраев (medium)**: паттерн `try: raise self.retry(exc=exc); except MaxRetriesExceededError: return sentinel` был битым - Celery 5.6.3 на исчерпании перебрасывает ИСХОДНОЕ transient-исключение, а не `MaxRetriesExceededError` (подтверждено рантайм-репро), поэтому header-задача падала в FAILURE и chord-callback не выстреливал. Починено явной проверкой `self.request.retries >= self.max_retries` до `retry`. **Тот же латентный баг был в M1/M2** (`score_article`/`extract_article`/`ingest_source`) - тоже починен (у дневного DAG смягчался реапером `stale_running`, у on-demand генерации реапера нет).

### Проверка M3

```bash
make lint                 # ruff чисто
make test                 # unit: + test_generation.py; M1/M2 остаются зелёными
make test-integration     # RUN_DB_TESTS=1: + test_generation_run.py (scored->drafted, posts-маппинг, drafted-счётчик, идемпотентность)
```

E2E на реальной инфре (сильная модель, `OPENAI_API_KEY` уже в `services/api/.env`):
```bash
make up && make worker    # Redis + worker (очереди default/fetch/extract/score/generate)
# 1) получить scored-статьи: дневной прогон
curl -XPOST localhost:8000/internal/pipeline/run -d '{"tenant_id":"<uuid>"}' -H 'content-type: application/json'
# 2) сгенерить черновики по требованию
curl -XPOST localhost:8000/internal/pipeline/generate -d '{"tenant_id":"<uuid>"}' -H 'content-type: application/json'
# проверить: articles.status='drafted'; posts (body_markdown/faq/json_ld/seo.brand_tie_in/suggested_titles/ai_model/ai_cost_usd);
#            ai_usage(stage='draft', pipeline_run_id); pipeline_runs.drafted
```
Синхронная альтернатива без брокера - `run_tenant_generation_sync(tenant_id)`. Живой LLM драфтинга: `RUN_DB_TESTS=1 RUN_LIVE_LLM=1 OPENAI_API_KEY=... pytest -q -m live`.

### Хвосты M3 (follow-ups, не блокеры)

- **Реапер зависших `drafting`**: при жёстком крэше воркера между claim (`scored -> drafting`) и финалом статья застревает в `drafting` (graceful-сбои LLM откатываются штатно). Нужен catch-up по аналогии с `stale_running` (сброс старых `drafting -> scored`). Требует `drafting_at`/по `updated_at`; в MVP редкий кейс, ручной сброс SQL.
- **Регенерация** уже сдрафтованной статьи (`force`-флаг / сброс `drafted -> scored`) - для редактора M4. Сейчас claim-guard даёт ровно один черновик на статью.
- **Мультилокальность**: один черновик в `locales[0]`; пост на каждый locale - аддитивно (нет unique на `article_id`).
- **Отдельный `pipeline_run` для генерации** (ledger-строка «generation run») - если понадобится наблюдаемость активности генерации сверх `posts`+`ai_usage`. Сейчас стоимость атрибутируется прогону, что заскорил статью.
- **Семантика `pipeline_runs.scored`**: после `scored -> drafted` счётчик `scored` прогона остаётся резидуальным (консистентно с уже резидуальным `extracted` после скоринга); `drafted` наполняется через `refresh_drafted`.

См. также `docs/04_mvp_spec.md` §7 и матрицу расширяемости `docs/07_m1_ingestion_plan.md` §10.

## Статус M4 (UI: дашборд, редактор, настройки, фидбэк) — готово

Веха M4 реализована целиком по плану `.claude/plans/docs-handoff-md-compiled-candy.md`. Маркетолог теперь работает поверх готового пайплайна как редактор (approve / edit / kill).

Архитектурный принцип соблюдён: web ходит НАПРЯМУЮ в Supabase под `authenticated` для всего тенант-скоупленного (RLS изолирует), три «тяжёлых» действия (`pipeline/run`, `pipeline/generate`, `sources/test`) идут через Next.js BFF (server actions) к FastAPI, `tenant_id` резолвится на сервере из `users` (`getUserAndTenant`), никогда из клиента.

Что сделано:
- **Каркас**: `flowbite-react` поднят до 0.12 (React-19-совместимость, plugin-setup для Tailwind v3 + `withFlowbiteReact`, `ThemeModeScript`/`ThemeInit`), route group `(app)` с shell (navbar/sidebar/локаль-свитчер), `getUserAndTenant`, BFF `lib/api/internal.ts` (`AbortController`-таймауты, коды мапятся в i18n), типы Supabase (`database.types.ts`, make-таргет `db-types`), Vitest jsdom+RTL.
- **Дашборд**: RSC-чтение posts+articles+scored-кандидатов, `PostCard` (бейджи приоритета/скора, действия), `StatusSection`, `DraftsBoard` (props-driven c картой optimistic-override — без клоббера соседних карточек), `ScoredCandidates` (генерация по выбору), `RunPipelineButton`.
- **Редактор**: `PostEditor` (автосейв debounce+blur+перед сменой статуса, flush-гард — статус не двигается поверх несохранённого контента), `MarkdownField` (`@uiw/react-md-editor`, ssr:false, тема через класс `dark`), `SeoPanel`, `FaqEditor`, `JsonLdPreview` (валидность+a11y), `StatusBar` (машина состояний), `ExportMenu` (Markdown/HTML/copy; HTML санитайзится rehype-sanitize, json-ld безопасно сериализуется, `<html lang>` из языка поста).
- **Relevance/фидбэк**: `RelevancePanel` (критерии итерируются динамически, без хардкода имён), `SourceOriginal`, `ScoreFeedback`/`DraftFeedback` (edited_diff через jsdiff), роут `articles/[id]`.
- **Настройки**: `BrandProfileForm`+`VoiceExamplesEditor` (RLS upsert по `tenant_id`), `SourcesSection`/`SourceForm` (динамическая форма из `config_schema` адаптера)/`SourceTestResult`, новый `GET /internal/adapters` (`REGISTRY.describe()`, секреты вырезаны) + fallback-константы.
- **i18n/тема/тесты**: полные `messages/{en,ru}.json` (паритет держит тест), тёмная тема, error-boundary `(app)/error.tsx` (DB-ошибка не маскируется под «пусто»), 36 web-тестов (чистые билдеры export/diff/status/types/adapters + компонентные DraftsBoard/ScoredCandidates/SourceTestResult).

### Независимый ревью M4 и починенные баги

Прогнан оркестрованный adversarial-review: 6 ортогональных линз (data-contract, react/next/flowbite, i18n, ux/a11y, bff-контракт, конкурентность) × верификация каждой находки — **21 подтверждённый дефект, все починены**. Ключевые (medium): dead-click в `ScoreFeedback` (comment-only не отправлялся), `generateDrafts`/`runPipeline` рапортовали успех при `queued:false` (HTTP 200), клоббер соседних карточек в `DraftsBoard` при откате, смена статуса поверх несохранённого контента в редакторе, отсутствующие accessible-name у icon-кнопок. Остальное (low): `<html lang>` в экспорте, гидратация дат (timeZone UTC), a11y (aria-labels, live-регионы, aria-pressed), маскировка DB-ошибок. Плюс баг из живого E2E: тема md-редактора не совпадала с приложением.

Отдельный security-review (изоляция тенантов / auth-IDOR / XSS-BFF): из находок подтверждена **1** — SSRF в fetch-слое (spoofing `tenant_id`, IDOR, XSS, auth-гарды — опровергнуты, посадка чистая).

- **SSRF (medium, было латентно с M1, M4 сделал достижимым из UI)**: `/internal/sources/test` и дневной ingestion фетчили произвольный URL пользователя без egress-фильтрации и эхоили `body_preview`/текст исключения — тенант мог пробить внутреннюю сеть (`169.254.169.254` и т.п.). Починено на уровне fetch-слоя (`app/fetch/guard.py::assert_public_url`/`safe_get`): блок не-http(s) схем и хостов, резолвящихся в loopback/link-local/private/reserved, валидация каждого редирект-хопа (авто-редиректы выключены), подключено в `HttpxFetcher`/`sitemap._download`/`crawl4ai`/`rss`; тест-эндпоинт больше не эхоит сырой текст исключения (opaque-код). Живьём проверено: внутренние цели блокируются без утечки, публичные источники работают. Хвост: IP-pinning против DNS-rebinding (узкий TOCTOU) — follow-up.

### Проверка M4

```bash
cd apps/web && pnpm typecheck && pnpm test && pnpm build   # tsc + 36 vitest + Next build
make lint                                                  # web eslint + api ruff (в CI venv активен)
cd services/api && . .venv/bin/activate && pytest -q -m "not integration and not live"   # 106 passed
```

E2E прогнан в браузере (Chrome DevTools MCP) на реальной инфре: регистрация → провижининг тенанта → настройки (бренд-профиль RLS-upsert, добавление RSS-источника + dry-run Test через BFF→FastAPI→адаптер, RLS-insert) → Run pipeline (BFF) → дашборд с данными (PostCard/ScoredCandidates) → редактор (табы, md-превью, FAQ, JSON-LD, RelevancePanel с динамическими критериями) → смена статуса new↔in_progress (RLS UPDATE + автосейв) → фидбэк (score comment-only, rating=null в БД) → RU-локаль. Консоль без ошибок; каждая починка перепроверена с подтверждением в БД.

Хвосты M4 (follow-ups, не блокеры): SSRF IP-pinning против DNS-rebinding; Realtime-обновление дашборда вместо ручного refresh; owner-only гейтинг действий; визард-онбординг вместо одностраничных настроек.

## Статус M5 (админка + метеринг-репорты: usage/бюджет/апселл/hard-cap) — готово

Веха M5 реализована целиком по плану `.claude/plans/handoff-parsed-firefly.md`. Owner видит свой месячный AI-расход и % бюджета с эскалирующими плашками; платформенный админ видит всех тенантов, их расход/бюджет и переключает план/бюджет/порог; генерация черновиков блокируется при исчерпании бюджета.

**Бюджетная модель (решение владельца):** `ai_budget_usd_month` = usable месячный AI-бюджет = цена тарифа × (1 − гарантированная маржа 20%); pilot — фикс $15. Эскалация по `spend/budget`: ≥50% notice, ≥`upsell_threshold_pct` (дефолт 80) upsell, ≥100% blocked. Расход — compute-on-read агрегация `ai_usage` за календарный месяц UTC (без cron-сброса; `ai_spent_usd_month` остаётся derived/мёртвой). Каталог тарифов и пороги — `apps/web/src/lib/plans.ts` (`RESERVED_MARGIN_PCT=20`, `PLAN_CATALOG`).

Что сделано:
- **Схема** (`supabase/migrations/0005_metering.sql`, аддитивно/идемпотентно): control-таблица `platform_admins` (глобальные админы, RLS self-select `user_id=auth.uid()`, revoke all + grant select), 4 агрегационных RPC. Owner-RPC `tenant_month_spend()` / `tenant_month_usage_by_stage()` — **security invoker** (RLS `ai_usage` скоупит к своему тенанту), execute только authenticated. Admin-RPC `admin_tenant_report(since)` / `admin_tenant_usage_by_stage(tenant, since)` — **security definer** (обходят RLS для кросс-тенант отчёта), execute **только service_role**. RPC нужны, т.к. PostgREST не даёт `sum()` в `.select()` и `[api] max_rows=1000` обрезал бы client-side сумму.
- **Backend** (`services/api`): `app/metering.py` (`month_start_utc`, `budget_exceeded`), `repositories.tenant_month_spend`. Hard-cap в `app/api/routes.py::generate_drafts` — перед enqueue считает месячный spend и при `spent >= ai_budget_usd_month` возвращает `budget_exceeded=True`, не ставя в очередь. Гейтится **только генерация** (дорогая стадия), скоринг/ingestion не трогаются. `GenerateResponse.budget_exceeded` добавлено обратносовместимо.
- **Frontend owner** (`apps/web`): `lib/plans.ts`, `lib/usage.ts` (`usagePercent`/`usageLevel`/`formatUsd`/`monthStartIso`), страница `(app)/usage/page.tsx` (spend/бюджет/%, разбивка по стадиям, черновики за месяц, лимиты тарифа), компоненты `usage/UsageSummary` + `usage/UpsellBanner`. Тонкая эскалационная плашка в `(app)/layout.tsx` (подавляется на самой `/usage`). Sidebar-entry `usage`, сегмент в `middleware.ts`, namespace `usage` (en+ru). BFF `_actions/pipeline.ts::generateDrafts` мапит `budget_exceeded` → тост в `ScoredCandidates`.
- **Frontend admin** (`apps/web`): гейт `lib/auth/platform.ts` (`assertPlatformAdmin`/`isPlatformAdmin` по `platform_admins` через RLS self-select), роут-группа `(app)/admin/*` с вложенным layout-гейтом (не-админ → 404), список тенантов `admin/page.tsx` (service_role RPC), карточка `admin/[tenantId]/page.tsx` + `AdminTenantDetail` + форма `PlanBudgetForm` (смена плана префиллит дефолтный бюджет, override разрешён). Admin CRUD — server action `_actions/admin.ts::updateTenantPlan` под `createAdminClient()` (service_role), с независимым гейтом и валидацией plan/budget/threshold. Sidebar-entry `admin` показывается только платформенному админу. namespace `admin` (en+ru).
- **Операционка**: `make seed-admin EMAIL=you@example.com [DB=<url>]` — выдать платформенного админа (пользователь уже должен быть зарегистрирован). Управление админами через UI — вне M5.

### Независимый ревью M5 и починенные баги

Прогнан оркестрованный adversarial-review (4 ортогональных линзы: RLS/безопасность, backend/hard-cap, react/next/flowbite, i18n/бюджет-модель × верификация каждой находки). **3 подтверждено, все починены:**
1. **Кросс-тенант утечка через security-definer RPC (critical, найдено прямой проверкой БД до ревью).** `revoke execute ... from anon, authenticated` НЕ снимает дефолтный `EXECUTE` для роли `PUBLIC` (роли наследуют его через PUBLIC), поэтому `admin_tenant_report`/`admin_tenant_usage_by_stage` были вызываемы любым `authenticated` → обход RLS → чтение данных всех тенантов. Починено `revoke execute ... from public`; переверено (`has_function_privilege('authenticated', ...)=false`) и integration-тестом.
2. **Глобальный баннер бюджета не срабатывал (medium).** `layout.tsx` брал spend через `typeof spendResult.data === "number"`, но `numeric`-RPC приходит из supabase-js строкой → всегда 0 → плашка эскалации не показывалась нигде, кроме `/usage`. Починено на `Number(spendResult.data ?? 0)` (как для остальных DB-чисел).
3. **`usagePercent` округление + budget=0 (low).** `Math.round`+кап показывал «100%» при 99.6% (ещё не blocked); при `budget=0` бэк блокировал всё, а фронт показывал «ok». Починено: `Math.floor` (100% = реально исчерпано) и `budget<=0 → blocked/100` с гардом missing-data в layout (консистентно с бэкенд-hard-cap).

Прочие 11 находок отклонены верификацией как false-positive.

### Проверка M5

```bash
cd apps/web && pnpm typecheck && pnpm test && pnpm build      # tsc + 59 vitest (вкл. UpsellBanner/AdminTenantsTable компонентные) + Next build — зелёные
make lint                                                     # web eslint + api ruff+format — чисто
cd services/api && . .venv/bin/activate && pytest -q -m "not integration and not live"   # 116 unit
RUN_DB_TESTS=1 pytest -q -m integration                       # 19 integration (0 падений): вкл. метеринг-окно spend, RLS-скоупинг owner-RPC, отказ admin-RPC под authenticated, platform_admins self-select/no-write
```

Верификация безопасности прямой проверкой БД (read-only): `has_function_privilege` подтверждает `admin_*` RPC — execute только `service_role` (`auth_exec=f, anon_exec=f`), owner-RPC — только `authenticated`; `platform_admins` — RLS enabled + self-select, authenticated имеет только SELECT. Изолированные self-cleaning integration-тесты доказывают RLS-скоупинг метеринга end-to-end под ролью `authenticated`.

### Хвосты M5 (follow-ups, не блокеры)

- **Месячный сброс:** compute-on-read авто-сбрасывается на UTC-границе месяца; `ai_spent_usd_month` — мёртвая колонка (никто не читает). Нюанс: граница месяца в UTC, не в таймзоне тенанта.
- **TOCTOU hard-cap — закрыт (M5.1, DB-резервирование).** Строгий per-call энфорс скоринга и генерации на уровне БД: миграция `0006_budget_ledger.sql` вводит атомарный счётчик `tenant_budget_ledger(tenant_id, period 'YYYY-MM', spent_usd)` (ключ по периоду = бесплатный месячный сброс). В `llm/client.py` (единая точка LLM-вызовов) — паттерн **reserve → call → settle**: перед вызовом атомарно `reserve_budget` (guard `spent_usd < budget` в `insert ... on conflict do update where`, конкурентные вызовы сериализуются на строке → TOCTOU-гонки нет), при исчерпании → `BudgetExceededError`; после — сверка на факт (`settle_budget`, delta = факт − оценка), при сбое вызова — рефанд оценки. Оценки стоимости per-stage — `metering.STAGE_COST_ESTIMATE`. Стадии: `score_article`/`generate_article` ловят `BudgetExceededError` → sentinel `skipped: budget_exceeded` (не «failed», не ретрай); у генерации claim `drafting → scored` откатывается штатно. `ai_usage` остаётся для отчётов/апселла (per-stage), леджер — только энфорс (service_role, web не читает). Роутовый pre-check в `generate_drafts` (на `ai_usage`) остаётся как быстрый UX-фейл. LiteLLM virtual keys — не требуются (прагматичный путь без второй stateful-зависимости в горячем пути). Тесты: unit (`test_llm_client` блок, `test_metering` period/estimate) + integration (`test_budget_ledger`: атомарный блок/settle/рефанд/месячный сброс + обе стадии блокируются, статья остаётся в прежнем статусе).
- **Управление платформенными админами** — есть UI (`/admin/admins`, страница `admin/admins/page.tsx` + `PlatformAdminsManager`): список админов (service_role + embed email), выдать по email/отозвать через server actions `grantPlatformAdmin`/`revokePlatformAdmin` (гейт + защита от самоотзыва). `make seed-admin` остаётся для бутстрапа первого админа. E2E прогнан (grant/revoke двух тестовых юзеров, БД очищена).
- **Нет Realtime:** usage/admin-числа — снимок на запрос; owner рефрешит после асинхронной генерации.
- **Браузерный E2E M5 прогнан** (Chrome DevTools MCP, реальная инфра): регистрация → провижининг тенанта → `/usage` (pilot $0/$15, 0%, пустая разбивка) → `/admin` для не-админа = 404 → `make seed-admin` → sidebar Admin + список тенантов → карточка (лимиты pro $129/20/250) → смена плана pro (бюджет автоподставился $103.20) → save → БД обновлена → override бюджета 0 → save → hard-cap: `/internal/pipeline/generate` вернул `budget_exceeded:true, queued:false` (бюджет проверяется раньше count) → blocked-баннер на `/usage` («Monthly budget reached», 100%) → кросс-апповая плашка на dashboard с CTA «View usage». Тестовый тенант удалён, БД чистая. Примечание: UI-кнопка генерации требует scored-статей (в песочнице нет DNS для пайплайна), поэтому UI-тост hard-cap не кликался — сам эндпоинт и blocked-баннер проверены.
- **Починены 7 pre-existing integration-тестов** (не были M5-багом): RSS-адаптер зовёт `assert_public_url` (M4 SSRF-guard, всегда включён, не гейтится `ingestion_guards_enabled`), а `.test`-домены не резолвятся в песочнице (`dns_error`) → `fetched:0`. Добавлена autouse-фикстура `_allow_test_hosts` в `test_scoring_run`/`test_generation_run`/`test_ingestion_ac1`, мокающая `app.adapters.rss.assert_public_url` (паттерн `test_health`). Прод-SSRF не ослаблен. Полный сьют зелёный: **116 unit + 19 integration**.

Дальше - M6 (пилот LOOTON) и роадмап (автопубликация в CMS, соцсети, Stripe-биллинг фазы 1.5).

## M6 — пилот LOOTON: входные данные и сухой прогон

Получены материалы от Kate: доки «Источники для парсера новостей LOOTON» и «Критерии отбора», плюс таблица voice-examples «инфоповод → статья». Прогнан сухой прогон пайплайна на реальных источниках (скрипты в scratchpad: `probe_feeds.py`, `probe_extract.py`, `probe_score.py`; исходящая сеть в среде есть).

### Скоринг: критерии Kate ложатся на нашу модель 1:1
Док «Критерии отбора» = `RelevanceScore` без изменений кода: 11 критериев (news/resale/commercial/trend + trend_explanation, seo/aeo/content/content_cluster/knowledge_gap/unique_angle) + `publication_priority` HOT/WARM/COLD/DROP + overall_score 0-100 + passes_threshold + decision_summary. `SYSTEM_TEMPLATE` в `scoring.py` уже несёт LOOTON-рамку («главный редактор... инфоповоды, после которых захочется найти/купить/продать/переоценить»). Бренд-профиль LOOTON (company/audience/filter_criteria/веса) настраивается из этого дока.

### Сухой прогон на реальных данных
- **Ingest (RSS-адаптер) работает** — 11/19 кандидатов живые/свежие (<3ч), багов на реальных фидах нет.
- **Extract работает** — httpx+trafilatura чисто тянет полный текст WWD (4171), GQ (3391), Vogue (13559), Glossy (5055); full-body-RSS источники гидратации не требуют. Fashionista антиботит статью (403), но тело есть в RSS.
- **Скоринг работает** — на реальных статьях валидный RelevanceScore с in-brand reasoning.
- **Вскрыто (задача калибровки M6): скоринг слишком «добрый».** Все 4 пробных статьи → overall 74-90, priority HOT/WARM, никто не COLD/DROP; маркетинг-история про running-бренд (Glossy, 90/HOT) обогнала sneaker-релиз (78). Правится: ужесточить filter_criteria, поднять/настроить score_threshold, добавить веса против не-ресейл тем + фидбэк Kate. **Оговорка:** прогон шёл на `gpt-5-mini`, т.к. gemini free-tier исчерпал квоту (429); сильная reasoning-модель дорисовывает угол ко всему → щедрее. Калибровать надо на продакшен-модели (`gemini-2.0-flash-lite`). Побочно: при переключении скоринга на reasoning-модель нужен `max_tokens` выше 2048 (иначе `IncompleteOutputException`).

### Валидированные источники (11 рабочих RSS для старта пилота)
Full-body RSS (extract не нужен): Hypebeast `https://hypebeast.com/feed`, Highsnobiety `https://www.highsnobiety.com/feed/`, Sneaker News `https://sneakernews.com/feed/`, Fashionista `https://fashionista.com/feed`, Glossy `https://www.glossy.co/feed/`, The Industry Fashion `https://www.theindustry.fashion/feed/`.
Через httpx-гидратацию: WWD `https://wwd.com/feed/`, GQ `https://www.gq.com/feed/rss`, Vogue `https://www.vogue.com/feed/rss`, Nice Kicks `https://www.nicekicks.com/feed/`, Business of Fashion `https://www.businessoffashion.com/feed/` (пейволл — только тизер).
Не отдали RSS (нужен news-sitemap/скрапер или фаза 2): Complex, Vogue Business, ресейл-маркетплейсы (StockX/RealReal/Grailed/Depop). Соцсети/SEO-тулы (доки §5-9) — вне MVP.

### Voice-examples от Kate — ПОЛУЧЕНЫ чистым файлом (блокер снят)
Ранее CSV пришёл в mojibake (UTF-8 как cp1252, ~половина кириллицы билась в `�`) — тексты было не восстановить. **Владелец приложил чистый PDF «примеры инфоповодов»**: таблица `Тип инфоповода | URL | Почему/угол LOOTON | Текст LOOTON`, ~8 заполненных постов + ~8 плановых типов, кириллица читается. Тексты перенесены в `services/api/scripts/looton_seed.json` в формат `{post_text, source_url, why}` (генерация берёт первые 3 через `_format_examples[:3]`). Блокер стадии генерации снят.

Заполненные примеры (URL + тип; тексты — ждём чистый файл):
1. Смена креативного директора — Salomon (Хейкки Салонен): `https://hypebeast.com/2026/1/heikki-salonen-salomon-creative-director-interview-info`
2. Новый показ — Prada SS27 menswear: `https://www.vogue.com/fashion-shows/spring-2027-menswear/prada`
3. Новый тренд сезона (вьетнамки/flip-flops): `https://www.vogue.co.uk/article/how-to-style-flip-flops`
4. Коллаборация (архивная модель) — CDG HOMME × New Balance 1226: `https://hypebeast.com/2026/6/comme-des-garcons-homme-new-balance-1226-new-silhouette-collaboration-paris-fashion-week-ss27-exclusive-first-look`
5. Релиз кроссовок — Nike Air Foamposite «Glow»: `https://hypebeast.com/2026/6/nike-air-foamposite-pro-prm-glow-in-the-dark-iv6246-100-release-info`
6. Релиз по мотивам фильма (поп-культура) — Nike AF1 «Ghostface»: `https://hypebeast.com/2026/7/nike-air-force-1-low-ghostface-summit-white-metallic-silver-black-gym-red-metallic-cool-grey-iv6350-121-official-images`
7. Запуск саб-бренда/линейки — Off-White L/AB: `https://hypebeast.com/2026/6/off-white-lab-co-label-launch-collection-release-info`
8. Изменение правил маркетплейса — Depop (комиссия): `https://www.news.com.au/lifestyle/fashion/fashion-trends/too-little-too-latefashion-platform-announces-huge-shakeup/news-story/3e2ca6fc561ff147d9123d0517a53fec`
9. Возвращение силуэта — skinny jeans: `https://www.g-star.com/en_fr/stories/denim/skinny-jeans-are-back`
10. Запуск новой категории — Off-White «TIME» (часы): без URL

Плановые типы (угол намечен, текст будет): юбилей культовой модели; фильм/сериал сделал вещь популярной; смерть/юбилей дизайнера; новая коллекция люкс-бренда; архивная выставка бренда; резкий рост цены культовой вещи; вирусный TikTok-тренд; тренд снимает модель с производства.

### Реализация M6 (сид + правки промптов) — сделано
Инженерная часть пилота, что можно построить без ключей владельца:
- **Идемпотентный сид LOOTON.** `services/api/scripts/looton_seed.json` (данные бренда как данные: тенант ru/Europe-Moscow, `company_description`/`audience_description`, жёсткий `filter_criteria` «берём/дропаем», `criteria_weights` с перекосом на resale/commercial/unique_angle, `score_threshold=75` (стартовое, финал за Kate), `voice_config{tone, unique_angle_hint}`, `locales=['ru']`, 9 voice_examples из PDF, 11 RSS-источников с priority/category). `services/api/scripts/seed_looton.py` — upsert под `session_scope` (bypassrls). Таргетинг тенанта детерминированный (имя — свободный текст, по нему молча не матчим): прод — `--owner-email` (резолв по владельцу) или `--tenant-id`; чистая БД — `--create`; без флагов и без существующего тенанта — падает (fail loud), orphan не плодит. По умолчанию create-only: существующие профиль/источники не трогаются (калибровка оператора в UI сохраняется), `--force` перезаписывает из JSON. Локально `make seed-looton`; прод `make seed-looton DB=<url> ARGS="--owner-email kate@..."`.
- **Промпт генерации доработан** (`pipeline/generation.py`): в system добавлены `company_description` + `audience` (раньше шли только в скоринг), few-shot теперь показывает модели `source_url` инфоповода рядом с текстом (связка «инфоповод → пост»). `docs/05` §4 синхронизирован (schema `language`/`meta_description=200`, шаблон).
- **Скоринг против завышения** (`pipeline/scoring.py`): в `SYSTEM_TEMPLATE` добавлена генерическая (тенант-агностичная) рамка строгости — не завышать, `high` только при явном сигнале, HOT только на прямое попадание в критерии, иначе DROP. LOOTON-специфика — данными (жёсткий `filter_criteria` + веса + порог 75).
- **Тесты.** `test_seed_looton.py` (структура JSON, формат voice_examples, отсутствие mojibake, 11 источников, совпадение ключей `criteria_weights` с критериями `RelevanceScore`, идемпотентность upsert на fake-сессии: fail-loud/create-only/force/owner-email), обновлён `test_generation.py` (company_description/audience/source_url + чистый рендер voice_config без дублей).
- **Порядок запуска пилота:** Kate регистрирует тенант LOOTON в web (создаст owner-логин), затем `make seed-looton DB=<prod> ARGS="--owner-email kate@..."` дозаполняет профиль/источники по владельцу. Направление шкалы `sources.priority` принято higher=trusted (сверить с конвенцией доков Kate).
- **Adversarial-ревью (3 линзы + верификация каждой находки).** 5 находок подтверждено и починено: (1) HIGH — сид матчил тенант по свободному имени → чинено детерминированным таргетингом по owner-email/tenant-id + fail-loud; (2) LOW — повтор затирал калибровку оператора → create-only по умолчанию, overwrite только под `--force`; (3) MEDIUM — `voice_config` уходил в промпт как Python-repr + дубль `unique_angle_hint` → рендер только tone; (4,5) LOW — добавлены тесты весов и идемпотентности. Все сценарии перепроверены в изолированном docker.

### Что нужно, чтобы запустить пилот
1. ~~Чистый перезалив voice-examples~~ — **сделано** (PDF → `looton_seed.json`).
2. **Платный tier gemini** (или сменить скоринг-модель) — free-tier умирает после нескольких вызовов (429).
3. **Hosted Supabase + деплой** — ключи владельца; после деплоя прогнать `make seed-looton DB=<prod_url>`.
4. **Решение Kate:** финальные `score_threshold`/приоритет (только HOT или HOT+WARM), веса критериев (стартовые значения — в `looton_seed.json`, правятся в UI настроек).
5. Калибровка скоринга на реальном потоке (первая неделя, на продакшен-модели `gemini-2.0-flash-lite`).

## Launch-подготовка: ревью + UX + launch-blockers + биллинг/триал + email — готово

Параллельный трек подготовки к боевому запуску (не путать с «M6 — пилот LOOTON» выше — это про данные пилота). Детальный план, решения и pre-deploy чеклист — `docs/09_launch_plan.md`. В плане работы пронумерованы M6.0-M6.3. Проверено локально: **API 154 unit-теста + ruff (lint+format), web tsc + lint + 68 тестов**. Миграции: `0007_reliability.sql`, `0008_billing.sql`, `0009_email.sql`. Integration-тесты (нужен Supabase-стек) и живой e2e (Stripe/Resend с ключами) — на этапе деплоя.

### Независимый ревью (7 измерений, каждая находка адверсариально верифицирована по коду)
Прогнан multi-agent ревью (бюджет/метеринг, RLS/authz, ingestion, scoring/generation, SSRF/fetch, web-actions, deploy/CI). **13 подтверждённых находок** (1 отклонена верификатором). Чисто (находок нет): RLS/мультитенант-изоляция, платформенные админы, chord-барьеры ingestion, атомарный claim генерации, provisioning тенанта. Launch-blockers из ревью починены в M6.1, остаток корректности (#8/#9/#13) отложен в M6.4.

### M6.0 — UX-фикс
`apps/web/src/app/[locale]/(app)/layout.tsx`: убран `mx-auto max-w-7xl` со shell (сайдбар прижат к левому краю, зазор на широких экранах убран), контенту дан воздух со всех сторон (`px-6 py-8 lg:px-8`) и верхний отступ, upsell-баннер перенесён в колонку контента.

### M6.1 — launch-blockers (деньги/безопасность/деплой), гейт прода — миграция `0007_reliability.sql`
`0007`: claim-статус `scoring` (симметрично `drafting`) + `articles.status_changed_at` (для reaper). Починки:
- **#1 (деньги)** `llm/client.py`: bookkeeping после оплаченного LLM-вызова (`_record_usage`/`_settle_reservation`) сделан best-effort — его сбой больше не пробрасывается, иначе `generate_draft_run` откатывал claim и статья перегенерилась (двойное списание). `HARD_CAPPED_STAGES` в `metering.py`.
- **#7** `llm/client.py`: ledger-reserve только для стадии `draft` (вне триала) — скоринг больше не падал в `BudgetExceededError` при добитом бюджете и не застревал в `extracted`.
- **#2 (деньги)** `pipeline/scoring.py`: рестрактор на session_factory-паттерн с атомарным pre-LLM claim `extracted → scoring` (как у генерации) — конкурентные прогоны одного `run_id` (re-dispatch «медленного, но живого» прогона) больше не скорят статью дважды. Репо: `claim_for_scoring`/`release_scoring_claim`, `advance_scored` guard `scoring`.
- **#3 (деньги+данные)** `pipeline/generation.py`: персист черновика с ретраем транзиентного сбоя, при неудаче — release claim (не застревает в `drafting`); beat-reaper `reap_stale_claims` (каждые 5 мин) освобождает застрявшие `scoring`/`drafting` по `status_changed_at` (порог `claim_stale_minutes=30`, заведомо больше времени сильной модели).
- **#4/#5/#10/#11 (SSRF)** `fetch/guard.py`: IP-pinning (резолв один раз, коннект на проверенный публичный IP, Host/SNI = хостнейм — закрыт DNS-rebinding); `adapters/rss.py` качает фид через `safe_get` (не даём feedparser ходить в сеть в обход guard); `worker/robots.py` — robots.txt через `safe_get`; `fetch/crawl4ai_fetcher.py` — пост-проверка финального URL (редирект в приватную сеть отбрасывает контент).
- **#6 (деплой)** `Makefile`: `db-migrate` теперь `set -e` + `psql -v ON_ERROR_STOP=1 --single-transaction` — битая миграция валит `migrate`-джоб и гейтит деплой (раньше exit 0 → деплой на немигрированную прод-БД).
- **#12 (деплой)** `main.py`: новый `/ready` с реальной пробой БД (`SELECT 1`) + Redis PING (503 при падении); `/health` остаётся liveness; web `/api/health` пробит upstream API; `deploy/compose.yml` api-healthcheck переключён на `/ready`.

### M6.2 — биллинг + триал (card-first Stripe test-mode) — миграция `0008_billing.sql`
Решения: гибрид-триал **7 дней / $3 hard-cap / 10 черновиков / 3 источника**, воронка **card-first (native Stripe `trial_period_days`)**, Stripe в **test mode на проде** (флип на live — заменой секретов, перед рекламой). Stripe = источник правды по плану/статусу, мост в наш ledger — одно число `ai_budget_usd_month`.
- `0008`: на `tenants` — `stripe_customer_id/subscription_id`, `subscription_status`, `current_period_end`, `trial_ends_at`, `billing_enabled` (allowlist Checkout), `trial_drafts_limit/sources_limit`; control-таблица `stripe_events` (дедуп вебхуков, только service_role).
- **Python-энфорс** (`llm/client.py` `_reserve_budget`): на триале (`subscription_status='trialing'`) гейтится и `score` (единый $3-cap ограничивает суммарный COGS), период ledger — фиксированный `'trial'` (не рефилится на стыке месяцев), expiry-guard `TrialExpiredError` (подкласс `BudgetExceededError`); trial drafts-лимит — в `/internal/pipeline/generate` (`PostRepository.count_posts`), trial sources-лимит — в web `upsertSource`.
- **Stripe в web** (единственный внешне доступный сервис): `lib/stripe/config.ts` (режим из префикса ключа `sk_test_`/`sk_live_` — «режим» и ключи не рассинхронятся; price-иды через env), `_actions/billing.ts` (Checkout с `trial_period_days`, гейт `billing_enabled`; Billing Portal), `api/stripe/webhook/route.ts` (claim-дедуп по `event.id` в `stripe_events`, при сбое хендлера claim удаляется для Stripe-ретрая; `lib/stripe/provisioning.ts` маппит подписку → `plan`/бюджет/статус: trialing→$3, active→бюджет тира, canceled/unpaid→pilot/0).
- **UI**: `billing/page.tsx` + `components/billing/BillingPanel.tsx` (карточки тарифов, статус, trial-meter, Manage Billing), site-wide **TEST MODE** баннер в layout (из префикса ключа), nav-entry `billing`, «start trial» баннер для новых тенантов, i18n `billing` (ru/en).
- **Card-first safety**: регистрация (`auth/actions.ts`) даёт новому тенанту `ai_budget_usd_month=0` — self-serve не жжёт AI без карты/триала; пилот провижинит админ.

### M6.3 — email-уведомления (Resend) — миграция `0009_email.sql`
Архитектура: email-логика (suppression/preferences/Svix-верификация) целиком в Python/Celery; web — тонкий прокси для внешне-доступного вебхука/отписки (зеркально Stripe). Resend Pro. Deps: `resend`, `jinja2`, `svix`.
- `0009`: `email_preferences` (per-type тумблеры + `unsubscribe_token`), `email_suppression` (bounce/complaint, глобально-unique, pre-send фильтр), `email_dispatch_log` (идемпотентность + аудит, unique `(user_id, notification_type, dedup_key)`).
- **Модуль** `app/email/`: `templates.py` (Jinja2-layout, ru/en, safe-escaping), `client.py` (send: suppression → digest opt-out → claim-идемпотентность insert-before-send → resend → mark/release), `notifications.py` (4 типа контента), `EmailRepository`.
- **Уведомления**: welcome (из web-регистрации через `/internal/notify/welcome`), digest (после `finalize_run_task`, dedup по `run_id`), trial-ending и budget-threshold (beat `scan_email_notifications` ежечасно, 50/80/100%). Очередь Celery `emails` + beat-расписание; deploy worker слушает `emails`.
- **Вебхук/отписка**: web `api/resend/webhook` и `api/unsubscribe` (GET-страница + POST one-click) проксируют на Python `/internal/email/webhook` (Svix-проверка по сырому телу → suppression) и `/internal/email/unsubscribe` (по токену). `List-Unsubscribe` + `List-Unsubscribe-Post` на digest.

### Открытая развилка (test-mode + карта-вперёд) — решена: вариант A
Владелец: строим систему сразу как положено (card-first Stripe trial), test mode — для внутренней обкатки на тестовых картах (`4242...`), перед рекламой флип на live. Публичного no-card триала не будет. Следствие: пока `sk_test_`, реальные карты Stripe не проходят — публичную рекламу до флипа не запускать. В коде вариант A реализован полностью, дописывать нечего.

### Pre-deploy чеклист (детали в `docs/09`)
1. Применить миграции 0007-0009 (схема раньше кода; `db-migrate` fail-fast). 2. `make test-integration` на Supabase-стеке. 3. Stripe test: Products/Prices + webhook `https://<domain>/api/stripe/webhook` + `STRIPE_*` env + `billing_enabled` приглашённым. 4. Resend: верификация домена (DKIM/SPF/DMARC), `RESEND_*`/`EMAIL_FROM`/`APP_BASE_URL`, webhook `https://<domain>/api/resend/webhook`. 5. Пилот LOOTON — провижининг админом (регистрация даёт бюджет 0). 6. Перед рекламой — флип Stripe test→live.

### M6.4 (находки 8, 9, 13) — готово
Верифицировано на изолированном docker-стеке (тот же, что M6.0-M6.3). Итог: API 157 unit + 34 integration + ruff/format чисто; web tsc + lint + 73 vitest.

- **#8** `adapters/sitemap.py`: в sitemap-index при `child_fetch_error` курсор `last_published_at` теперь НЕ двигается (флаг `child_failed`, `advance` только при полном успехе детей) — записи упавшего ребёнка дочитываются в следующий прогон (upsert идемпотентен), а не отсекаются как «старые». Регресс-тест `test_sitemap_fetch_does_not_advance_cursor_when_child_fails`. Осознанно НЕ распространяем guard на усечение `_MAX_CHILD_SITEMAPS` (>25 детей): это перманентное, а не транзиентное усечение, и guard там заклинил бы курсор навсегда (подтверждено adversarial-верификацией).
- **#9** `llm/client.py`: hook `completion:response` копит ВСЕ ответы Instructor (финал + ретраи валидации), `_record_usage` суммирует стоимость и токены по попыткам — hard-cap больше не недосчитывает ретраи в 2-4x. Adversarial-ревью вскрыло вторичный дефект и он тоже починен: на пути исчерпания ретраев (Instructor бросает) `except` рефандил резерв целиком и не писал usage — сожжённые деньги терялись мимо леджера; теперь при непустых `attempts` пишем их usage и сводим резерв к факту (полный рефанд — только если ни одного ответа не было). Тесты: `test_structured_completion_sums_retry_attempt_costs`, `test_records_paid_attempts_when_retries_exhausted` (unit) + `test_failed_call_with_paid_retries_settles_ledger_not_full_refund` (integration).
- **#13** `_actions/posts.ts`: `updatePostStatus` через compare-and-swap — UPDATE скоуплен `.eq("id").eq("status", from).select("id")`, при 0 затронутых строк возвращает `code: "conflict"` (потребители показывают общий error-тост и откатывают optimistic — новый code i18n не требует). Конкурентные легальные переходы больше не пишут поверх устаревшей проверки `canTransition`. Web-тест `posts.test.ts` (happy/conflict/illegal/notFound/updateFailed).

Adversarial-ревью диффа (3 линзы по фиксу + верификация каждой находки): 1 подтверждённый дефект (failure-путь #9) починен, находка по усечению #8 отклонена как некорректная (guard сломал бы адаптер), #13 — чисто.

### Изолированная верификация M6.0-M6.3 (dry-run на docker-Postgres) — готово

Пункты 1-2 pre-deploy чеклиста (миграции 0007-0009 + `make test-integration`) прогнаны на ИЗОЛИРОВАННОМ стеке, без касания общей dev-БД. Поднят голый `postgres:17-alpine` (БД `katesearches_verify`, отдельная docker-сеть) + project-named runner-контейнер (репо примонтировано read-only, `psql`/`make`/`pytest` внутри). Миграции завязаны на примитивы Supabase (роли `anon`/`authenticated`/`service_role`, `auth.uid()`, дефолтные привилегии), поэтому перед ними накатывается bootstrap-шим, воспроизводящий их 1:1. Шим сверен read-only с реальной Supabase (:54322): дефолтный ACL там `authenticated=arwdDxtm/postgres` (a/r/w/d/**D=truncate**/x/t/m), то есть новая таблица авто-получает у `authenticated` все привилегии, включая TRUNCATE — именно это защищают revoke-строки в миграциях.

Результаты:
- **Миграции 0001-0009 ложатся чисто.** Свежая БД через реальный `make db-migrate`: exit 0, 9 применено, 0 ошибок; повторный прогон идемпотентен (`already exists, skipping`). Проверена конкретика: 0007 — `scoring` в CHECK `articles.status` + колонка `status_changed_at` + partial-индекс `idx_articles_claimed`; 0008 — 8 billing/trial-колонок `tenants` + `stripe_events` (RLS on, `revoke all` от authenticated); 0009 — `email_preferences`/`email_suppression`/`email_dispatch_log` + unique `(user_id, notification_type, dedup_key)`.
- **`make db-migrate` реально fail-fast.** Битая миграция даёт `make: *** Error` и non-zero exit, прогон останавливается ровно на ней (rollback через `--single-transaction` + `ON_ERROR_STOP=1`); happy-path — exit 0. Деплой на немигрированную БД загейчен.
- **Тесты зелёные:** 33 integration (`RUN_DB_TESTS=1`) + 154 unit + ruff/format чисто.

Найдено и починено в ходе верификации:
- **Находка #1 (security, defense-in-depth) — починено в `0009_email.sql`.** `email_preferences` снимал у `authenticated` только `insert, delete`, оставляя **TRUNCATE** (обходит RLS — снёс бы предпочтения всех тенантов). Тот же класс дыры чинили в `0002` для content-таблиц (M1 #8), в `0009` пропустили. Добавлен `revoke truncate on email_preferences from authenticated` (SELECT/UPDATE RLS-скоупа сохранены). Пробел закрыт: `test_rls.py::test_m6_control_tables_reject_authenticated_writes` — authenticated не TRUNCATE'ит `email_preferences` и не пишет в `stripe_events`/`email_suppression`/`email_dispatch_log`.
- **Находка #2 (стухшие фикстуры, ломали 9 integration) — починены тесты.** M6.1 перевёл `adapters/rss.py` с `assert_public_url` на `safe_get`, но фикстуры `_allow_test_hosts` в `test_scoring_run`/`test_generation_run`/`test_ingestion_ac1` всё ещё мокали исчезнувший `assert_public_url` (падали на setup) и мокали `feedparser.parse` в обход нового `safe_get`. Продуктовый rss.py корректен — стухли тесты (integration гоняли только «на этапе деплоя»). Моки переведены на `safe_get` (fake-response несёт URL в `.content`).
- **Пробел покрытия (закрыт).** Рестрактор скоринга (`extracted→scoring→scored`) и trial-aware reserve unit-тестами против реальной БД не покрывались. Добавлен `test_trial_and_reaper.py` (7 тестов): score+draft на триале через единый ledger-пул `period='trial'`; вне триала score не гейтится, draft идёт по месячному периоду; единый $3-cap покрывает суммарный COGS обеих стадий; `TrialExpiredError` при истёкшем триале; value-fence лимита драфтов (override + дефолт `TRIAL_DEFAULT_DRAFTS_LIMIT`); `reap_stale_claims` (`scoring`→extracted с ре-энкью, `drafting`→scored, свежий claim не трогается).

Не покрыто этой БД-верификацией: **trial sources-лимит** — в web (`upsertSource`, TypeScript), нужен web-тест/e2e. Живой e2e Stripe/Resend с ключами — по-прежнему на этапе деплоя (пункты 3-4 чеклиста).
