# 08 — Спек деплоя и инфраструктуры

> Источник истины по тому, как KateSearches собирается, катится и живёт в проде и на staging. Опорные файлы в репозитории: `deploy/` (compose.yml, deploy.sh, traefik/, env.example, README.md), `.github/workflows/` (ci.yml, deploy-staging.yml, deploy-prod.yml), `apps/web/Dockerfile`, `services/api/Dockerfile`. Опорные доки: `03_architecture.md` (стек), `07_m1_ingestion_plan.md` (Celery-конвейер, который катится как worker/beat).

## 1. Что и куда деплоим

Продакшн и тестовое окружение крутятся на одной VM двумя изолированными compose-проектами. Образы собираются в GitHub Actions и пушатся в GHCR, VM их только `pull` и катит через `docker rollout`. Один общий Traefik держит TLS и разводит трафик по хостнеймам.

```
GitHub Actions ──build+push──> GHCR (ghcr.io/ipolotsky/kate-searches/{web,api})
       │                                   │
   CI (reusable ci.yml)                     │ docker compose pull
       │                                    ▼
       └──ssh──> VM ──> deploy.sh ──> docker rollout web,api  +  recreate worker,beat
                         │
   Traefik :80/:443 (shared, Let's Encrypt)
     taskyou.me           -> kate-prod_web:3000
     staging.taskyou.me   -> kate-staging_web:3000
   api/worker/beat/redis  -> только внутренняя сеть проекта (наружу не публикуются)
```

Триггеры пайплайнов:
- PR открыт или обновлён -> сборка образов -> миграции staging-БД -> rollout на общий staging -> бот постит в PR ссылку и чек-лист;
- merge в `main` -> сборка -> миграции прод-БД -> rollout на прод.

Реком. размер VM: 4 vCPU / 8 GB RAM / 40+ GB SSD плюс 2-4 GB swap.

## 2. Окружения: prod и staging на одной VM

Изоляция идёт через два compose-проекта поверх одного шаблона `deploy/compose.yml`:

| | prod | staging |
|---|---|---|
| compose-проект (`COMPOSE_PROJECT_NAME`) | `kate-prod` | `kate-staging` |
| домен | `taskyou.me` | `staging.taskyou.me` |
| БД | отдельный проект Supabase | отдельный проект Supabase |
| Redis | свой контейнер | свой контейнер |
| каталог секретов на VM | `/srv/kate-searches/prod/.env` | `/srv/kate-searches/staging/.env` |

Что даёт изоляция:
1. Раздельные Supabase-проекты - тестовые прогоны пайплайна не пишут в прод-данные.
2. Раздельный Redis на каждый проект - очереди Celery не пересекаются.
3. Раздельные docker-сети и имена контейнеров - окружения не видят друг друга.

Staging один и общий: любой открытый PR деплоится туда, при нескольких открытых PR стенд занимает последний задеплоенный. Это осознанный компромисс ради простоты (для команды из одного-двух человек нормально).

## 3. Docker-образы и стратегия слоёв

Два требования к образам: слои небольшие, и при изменении кода зависимости (`.venv`/`node_modules`) не переустанавливаются. Оба решаются multi-stage сборкой с правильным порядком слоёв: сначала копируется манифест зависимостей и ставятся зависимости (кэшируемый слой), потом копируется исходный код (отдельный слой).

### web (`apps/web/Dockerfile`, контекст = корень репозитория)

Три стадии: `deps` (ставит workspace-зависимости pnpm, слой кэшируется по `pnpm-lock.yaml`) -> `builder` (`next build` в режиме standalone) -> `runner` (минимальный `node:22-alpine`, только `.next/standalone` + `.next/static` + `messages`). Итог: около 240 MB, старт за ~260 мс.

Тонкие места, которые уже учтены:
1. `next.config.mjs`: включён `output: "standalone"` и `outputFileTracingRoot` на корень монорепы (иначе hoisted-зависимости pnpm не попадут в трейс).
2. `messages/{en,ru}.json` грузятся динамическим импортом по шаблонной строке и ненадёжно трейсятся - копируются в образ явно.
3. `NEXT_PUBLIC_SUPABASE_URL` и `NEXT_PUBLIC_SUPABASE_ANON_KEY` инлайнятся в клиентский бандл на этапе сборки, поэтому передаются как build-args. Следствие важное: **web-образ привязан к окружению** - staging и prod это разные образы с запечённым разным Supabase-проектом. Один web-образ нельзя катить в оба окружения.
4. `apps/web/public/` пока нет - строка `COPY public` в Dockerfile закомментирована, раскомментировать при появлении статики.
5. Healthcheck ходит на `/api/health` (роут в обход middleware, `apps/web/src/app/api/health/route.ts`).

### api (`services/api/Dockerfile`, контекст = `services/api`)

Две стадии: `builder` (venv + зависимости, build-tools остаются здесь) -> `runtime` (slim без build-tools, `app` импортится через `PYTHONPATH`). Итог: около 484 MB, работает под non-root `appuser`. Один образ обслуживает три роли (api, worker, beat), роль задаётся `command:` в compose.

Тонкие места:
1. Слой зависимостей: `pip install .` при наличии только `pyproject.toml` ставит зависимости из `[project.dependencies]` (пустой пакет собирается корректно), код добавляется следующим слоем. Не завязываемся на editable-`.pth`, который ломается при копировании venv между стадиями.
2. `lxml`/`psycopg[binary]` идут manylinux-колёсами, поэтому системные библиотеки в runtime-слое не нужны.
3. `crawl4ai`/Playwright намеренно не в образе (ленивый импорт, extra `[scraper]`). Если понадобится JS-рендер источников в проде, собирать отдельный тяжёлый образ worker с `pip install .[scraper]` и `playwright install --with-deps chromium`, api и beat оставить на лёгком образе.
4. `.dockerignore` обязателен и уже добавлен: без него `COPY . .` тянет в слои `.venv`, кэши и `.env` с живыми ключами (утечка секретов).

### Проверено локально

- api: `/health` -> 200, healthcheck `healthy`, импорт `app` через PYTHONPATH, слой `pip install` кэшируется при правке кода.
- web: `/api/health` -> 200, `/` -> 307 (редирект на локаль), `messages` на месте, слой `pnpm install` кэшируется при правке кода.

## 4. Выкатка: docker rollout

Zero-downtime выкатка через плагин `docker-rollout` (scale-up новой реплики -> ждём healthcheck -> scale-down старой). Не все сервисы катятся одинаково:

| сервис | как катим | почему |
|---|---|---|
| `web`, `api` | `docker rollout` | stateless HTTP, healthcheck-gated, zero-downtime |
| `worker` | `up -d --force-recreate` | консьюмер очереди; вторая реплика при scale-up задваивает потребление |
| `beat` | `up -d --force-recreate` | строго один экземпляр; scale-up = два планировщика = дубли расписания |
| `redis` | не трогаем | stateful |

Обязательные условия для катимых через rollout сервисов (заданы в `deploy/compose.yml`): у `web`/`api` нет `container_name` и нет host `ports:` (иначе вторая реплика не поднимется), у обоих есть `healthcheck` (rollout ждёт именно его).

Безопасность фоновых задач при recreate worker: `stop_grace_period: 60s` даёт время на warm shutdown, а `acks_late` + `reject_on_worker_lost` + `visibility_timeout` (уже в `celery_app.py`) переотдают незавершённые задачи из Redis. Даже кратковременный простой worker безопасен - задачи ждут в очереди.

Скрипт выкатки - `deploy/deploy.sh <prod|staging> <web_tag> <api_tag>`. Порядок: пин тегов в `.env` -> `docker compose pull` -> `up -d redis` -> `rollout api` -> `rollout web` -> `recreate worker` -> `recreate beat` -> `image prune`. При первом деплое сервиса (rollout нечего масштабировать) скрипт делает обычный `up -d`.

## 5. CI/CD пайплайны

Три workflow. CI вынесен в переиспользуемый (`ci.yml` с триггером `workflow_call`), деплой-workflow его вызывают - линты и тесты гейтят выкатку.

### `deploy-staging.yml`

Триггер: `pull_request` в `main` (`opened`/`synchronize`/`reopened`/`ready_for_review`). Concurrency по номеру PR с `cancel-in-progress` - новый пуш в PR отменяет предыдущую выкатку. Черновые PR (draft) деплой не запускают, но CI на них прогоняется.

Джобы: `ci` (reusable) -> `build` (buildx, push `web:staging-<sha>` со staging build-args + `api:staging-<sha>`, кэш `type=gha`) -> `migrate` (миграции staging-БД) -> `deploy` (scp `compose.yml`+`deploy.sh` на VM, ssh -> `deploy.sh staging`) -> `comment` (sticky-коммент в PR: ссылка на staging + чек-лист).

### `deploy-prod.yml`

Триггер: `push` в `main`. Concurrency `deploy-production` без отмены. Те же джобы, но с прод-тегами и прод-секретами, без коммента. Оба образа пересобираются (api не промоутится ре-тегом ради простоты и предсказуемости).

### Описание PR

`.github/pull_request_template.md` задаёт секции «Что сделано» и «Что тестировать (по пунктам)» - заполняет автор PR. Бот отдельным комментом дописывает ссылку на staging и болванку чек-листа.

### Замечание про двойной прогон CI

Сейчас на `ci.yml` оставлены триггеры `push`/`pull_request` ради независимого зелёного бейджа во время начальной настройки, поэтому на PR CI идёт дважды (отдельно и внутри Deploy Staging). Когда staging-деплой устаканится, убрать `pull_request` из `ci.yml` - останется один прогон.

## 6. Миграции БД

Схема живёт в `supabase/migrations/*.sql` и накатывается на managed Supabase отдельным job `migrate` на раннере (`make db-migrate`, то есть `psql -f` по каждому файлу с `DATABASE_URL` из секрета окружения). Миграции идемпотентны (`if not exists`, `drop policy if exists`, `create or replace`), поэтому безопасно гонять на каждый деплой. Порядок: `migrate` перед `rollout`, схема раньше кода.

Дисциплина expand/contract: во время rollout старый код короткое время работает уже на новой схеме. Аддитивные изменения безопасны, деструктивные (drop/rename колонки) - в два деплоя: сперва код, который терпит обе схемы, потом миграция, позже удаление старого.

Миграции не гоняем из api-образа (там нет `psql`, только libpq через psycopg) - только с раннера.

## 7. Секреты и переменные окружения

Что где лежит:
- **GitHub Secrets** (в environment-скоупах `staging`/`production`): `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`; `STAGING_/PROD_NEXT_PUBLIC_SUPABASE_URL`, `..._ANON_KEY` (build-args web); `STAGING_/PROD_DATABASE_URL` (только для миграций). Плюс переменная `STAGING_URL` для коммента бота.
- **GHCR**: встроенный `GITHUB_TOKEN` с `permissions: packages: write`, отдельный PAT не нужен.
- **Секреты рантайма** (`SUPABASE_SERVICE_ROLE_KEY`, ключи LLM, `DATABASE_URL`, `FIRECRAWL_API_KEY` и т.д.): только в `/srv/kate-searches/{prod,staging}/.env` на VM, chmod 600. **В CI ключей LLM и service-role нет** - это принципиально.

Шаблон `.env` окружения - `deploy/env.example`. Один `.env` общий для web/api/worker/beat (через `env_file`), `REDIS_URL`/`API_BASE_URL`/`PORT` заданы в compose и в `.env` не дублируются.

## 8. Топология VM

Один общий Traefik на всю машину (не по одному на окружение) слушает 80/443, редиректит 80 -> 443, держит Let's Encrypt через TLS-ALPN. Роутинг по `Host`. `web` каждого проекта подключён к внешней сети `proxy`; `api`/`worker`/`beat`/`redis` живут только в приватной сети `internal` своего проекта и наружу не публикуются. Web ходит в api по внутреннему DNS `http://api:8000`.

Раскладка на VM:
```
/srv/
  traefik/
    docker-compose.yml      # deploy/traefik/docker-compose.yml
    acme.json               # chmod 600
  kate-searches/
    compose.yml             # синхронится из репо (scp) на деплое
    deploy.sh               # синхронится из репо (scp) на деплое
    prod/.env               # chmod 600, руками
    staging/.env            # chmod 600, руками
```

`compose.yml` и `deploy.sh` синхронизируются из репозитория на шаге деплоя, руками их на VM править не нужно. Устойчивость к сбою одного request web -> api в момент rollout api: rollout убирает старый контейнер только после healthy нового, плюс в `apps/web/src/lib/api/internal.ts` добавлен один ретрай на `networkError`.

## 9. Разовая подготовка VM

1. Docker и docker compose v2.
2. Плагин docker-rollout:
   ```bash
   mkdir -p ~/.docker/cli-plugins
   curl -fsSL https://raw.githubusercontent.com/wowu/docker-rollout/master/docker-rollout \
     -o ~/.docker/cli-plugins/docker-rollout
   chmod +x ~/.docker/cli-plugins/docker-rollout
   ```
3. Swap 2-4 GB (страховка на время rollout, когда web/api временно задваиваются).
4. Общая сеть: `docker network create proxy`.
5. Traefik:
   ```bash
   mkdir -p /srv/traefik && cd /srv/traefik
   # положить deploy/traefik/docker-compose.yml
   touch acme.json && chmod 600 acme.json
   docker compose up -d
   ```
6. Каталоги и секреты стека:
   ```bash
   mkdir -p /srv/kate-searches/prod /srv/kate-searches/staging
   # заполнить по образцу deploy/env.example, chmod 600:
   #   prod/.env      (STACK=kate-prod,    DOMAIN=taskyou.me)
   #   staging/.env   (STACK=kate-staging, DOMAIN=staging.taskyou.me, свой Supabase)
   ```
7. DNS: A-записи `taskyou.me` и `staging.taskyou.me` на IP VM.
8. Второй проект Supabase под staging: создать, прогнать миграции (`DATABASE_URL=<staging-db> make db-migrate`), взять URL/anon/service-role в `staging/.env`.
9. GitHub: завести секреты и переменную `STAGING_URL` (см. §7).

На время отладки роутинга включить в Traefik staging-CA Let's Encrypt (закомментированная строка в `deploy/traefik/docker-compose.yml`), потом вернуть боевой CA.

## 10. Runbook

- **Ручной деплой** (для отладки, обычно делает CI):
  ```bash
  /srv/kate-searches/deploy.sh staging staging-<sha> staging-<sha>
  /srv/kate-searches/deploy.sh prod    prod-<sha>    prod-<sha>
  ```
- **Откат**: перекатить предыдущий тег образа тем же скриптом, например `deploy.sh prod prod-<предыдущий-sha> prod-<предыдущий-sha>`. Образы в GHCR тегируются по каждому `sha`, откат это просто rollout старого тега.
- **Логи**: `cd /srv/kate-searches/<env> && docker compose logs -f <web|api|worker|beat>`.
- **Статус**: `docker compose ps` в каталоге окружения; health контейнеров - в колонке STATUS.
- **Проверка снаружи**: `curl -I https://taskyou.me` и `https://staging.taskyou.me` -> 200 и валидный TLS.
- **Переезд на новый домен** (`taskyou.me` -> `katesearch.es`): сменить `DOMAIN` в `.env` окружения, добавить A-записи, следующий деплой перевыпустит сертификат Traefik. Web-образ придётся пересобрать, если сменится и Supabase-проект (запечён `NEXT_PUBLIC_*`).

## 11. Риски и решения

1. Утечка секретов через `COPY . .` в api -> `services/api/.dockerignore`, секреты только в рантайме.
2. Web-образ привязан к окружению (запечён `NEXT_PUBLIC_*`) -> собирать web дважды, не промоутить между окружениями. Api-образ env-agnostic.
3. Двойной beat при rollout -> beat никогда не rollout, только recreate.
4. Потеря in-flight задач при recreate worker -> `stop_grace_period` + `acks_late`/`reject_on_worker_lost`, задачи переживают в Redis.
5. Потеря запроса web -> api в момент cutover -> rollout убирает старый контейнер после healthy нового + ретрай в `internal.ts`.
6. 8 GB под прод + staging + rollout-дубли -> swap + `worker --concurrency 2` (на staging ниже).
7. Деструктивные миграции под rollout -> дисциплина expand/contract (см. §6).
8. Права файлов -> `.env` и `acme.json` строго chmod 600 (Traefik иначе не читает acme.json).

## 12. Инфра-роадмап (пока не делаем)

- Ephemeral-окружение на каждый PR (свой поддомен и БД) вместо общего staging.
- Отдельный тяжёлый образ worker с crawl4ai/Playwright, если понадобится JS-рендер источников.
- Self-hosted LiteLLM + Langfuse рядом с api для метеринга и бюджетов per-tenant (в MVP-проде выключены: прямой SDK, `LANGFUSE_ENABLED=false`).
- Промоушен api-образа из staging в prod ре-тегом дайджеста вместо пересборки.
- Метрики/алерты (healthcheck-эндпоинты уже есть у web и api).
