---
type: Plan
title: План внедрения — OpenTelemetry + VictoriaLogs
description: Централизованная наблюдаемость KateSearches — OTel-инструментация web/api/worker/beat и лёгкий бэкенд логов VictoriaLogs на VM. Фазы A (логи) → B (трейсы) → C (метрики/алерты).
status: draft
tags: [tech, observability, plan, deployment]
generated:
  by: human:alexander.polyakov
  at: 2026-08-01
---

# План внедрения: OpenTelemetry + VictoriaLogs

> Централизованная наблюдаемость для KateSearches: единая инструментация через **OpenTelemetry**
> (traces / metrics / logs, vendor-neutral) и лёгкий бэкенд хранения логов **VictoriaLogs** на текущей VM.
> Решение зафиксировано в [ADR-0010](/adr/0010-observability-otel-victorialogs.md).
> Опорные доки: [деплой §8, §12](/deployment.md) (топология VM, инфра-роадмап), [архитектура §6](/architecture.md)
> (cost-metering через Langfuse — смежный, но отдельный контур), [ADR-0004](/adr/0004-litellm-gateway-langfuse-metering.md).

## 1. Зачем и критерий готовности

**Текущее состояние.** Единственный инструмент наблюдения в проде — `docker compose logs -f <web|api|worker|beat>`
([деплой §10](/deployment.md)). Это значит:

- логи эфемерны — теряются при `recreate`/`rollout` контейнера, истории нет;
- нет корреляции между сервисами: запрос `web → api → worker` невозможно собрать в одну нить;
- нет поиска/фильтра по `tenant_id`, `stage`, `request_id`, времени;
- нет трейсов (где узкое место конвейера) и метрик (латентность, ошибки, длина очередей Celery);
- алертов нет — падение узнаём постфактум.

**Langfuse — это не оно.** [Langfuse](/adr/0004-litellm-gateway-langfuse-metering.md) покрывает
**только LLM-контур** (cost/quality per tenant) и в MVP-проде выключен. Наблюдаемость приложения и инфры —
отдельная задача; она уже висит в [инфра-роадмапе §12](/deployment.md) строкой «Метрики/алерты». Этот план её закрывает.
Контуры **комплементарны**, а не заменяют друг друга (см. §9).

**Критерий готовности фазы A (MVP наблюдаемости):**

1. Логи всех четырёх сервисов (web/api/worker/beat) + Traefik access-логи собираются централизованно, переживают
   `rollout`/`recreate` и хранятся ≥ 7 дней.
2. Каждая строка лога структурирована (JSON) и несёт `service.name`, `env`, `trace_id`, `request_id`, `tenant_id`,
   `stage` (где применимо) — можно за один запрос LogsQL вытащить всё по одному тенанту/запросу.
3. Оба окружения (prod/stage) пишут в один стек, разделяются меткой `env`.
4. UI VictoriaLogs доступен снаружи только за Traefik + basic-auth.
5. Весь контур выключаем одним флагом `OTEL_ENABLED=false` без пересборки образов; в dev по умолчанию выключен.
6. Пиковое потребление RAM стека наблюдаемости ≤ 512 MB (VM 2 vCPU / 8 GB, свободно ~6 GB — [деплой §13](/deployment.md)).

Трейсы (фаза B) и метрики/алерты (фаза C) — вне MVP-скоупа наблюдаемости, но инструментация и Collector
закладываются так, чтобы включить их **без изменений в коде приложения** (в этом весь смысл OTel).

## 2. Ключевое решение: OTel как единый шов, VictoriaLogs как лёгкий бэкенд

**Почему OpenTelemetry.** Инструментируем один раз (SDK + авто-инструментация), а бэкенд можно менять/добавлять
конфигом Collector. Сегодня — логи в VictoriaLogs; завтра — трейсы в VictoriaTraces/Jaeger и метрики в
VictoriaMetrics без переписывания приложения. Не привязываемся к вендору.

**Почему VictoriaLogs (а не Loki / ELK).**

| Кандидат | Вердикт |
|---|---|
| **VictoriaLogs** ✅ | Один бинарь, без внешних зависимостей (не нужен object store/индекс), ~десятки MB RAM в покое, высокая компрессия, быстрый полнотекст через LogsQL, нативный **OTLP-приём логов**. Идеален под тесную VM. |
| Grafana Loki | Легче ELK, но тяжелее и капризнее VL (индекс/чанки, требователен к настройке label-кардинальности). |
| ELK / OpenSearch | JVM + гигабайты RAM — не влезает в 2 vCPU / 8 GB рядом с двумя app-стеками и Traefik. |

**Топология на VM.** Один **общий** стек наблюдаемости на всю машину (как один общий Traefik на оба окружения,
[деплой §8](/deployment.md)): один OTel Collector + один VictoriaLogs обслуживают и prod, и stage, разделяя данные
меткой `env`/`service.namespace`. Живёт отдельным compose-проектом в `/srv/observability/`.

```
                     ┌─────────────────── VM (одна машина) ───────────────────┐
  web (prod/stage) ──┐                                                          │
  api ───────────────┤ stdout(JSON) ──► [OTel Collector] ──OTLP──► [VictoriaLogs] ──► LogsQL UI
  worker ────────────┤     + OTLP traces/metrics (фазы B/C)              (retention 7–14d)   │
  beat ──────────────┘                     ▲                                   │            │
  Traefik access.log ──── filelog scrape ──┘                                   │        Traefik
                                                                               │      (basic-auth)
                     └───────────────────────────────────────────────────────┘
```

**Сеть.** Заводим внешнюю docker-сеть `obs` (по аналогии с `proxy`). Collector подключён к `obs`; app-контейнеры
получают членство в `obs` дополнительно к своей приватной `internal`. VictoriaLogs наружу не публикуется — только его
UI через Traefik. Collector слушает OTLP `4317/4318` внутри `obs`.

## 3. Пути доставки телеметрии

Осознанно разделяем логи и трейсы/метрики по способу доставки — ради устойчивости.

- **Логи → scrape (pull), не push.** Приложения пишут структурированный JSON в **stdout** (docker `json-file`
  драйвер сохраняется). Collector `filelog`-ресивером читает `/var/lib/docker/containers/*/*.log`, парсит JSON,
  обогащает docker-метаданными и шлёт в VictoriaLogs по OTLP.
  - Плюс: приложение не зависит от доступности Collector; `docker compose logs` продолжает работать; лог не теряется,
    если Collector в даунтайме (лежит в json-file, дочитается).
- **Трейсы/метрики → push (OTLP).** App-SDK экспортируют спаны/метрики напрямую в Collector `4317` (gRPC). Это
  best-effort по природе; логи (критичные для разбора инцидентов) от Collector не зависят.

Ограничить json-file драйвер (`max-size`/`max-file`) в compose, чтобы диск не рос: логи-источник ротируется docker'ом,
долгое хранение — на стороне VictoriaLogs.

## 4. Инструментация приложений

Общее правило: всё за флагом `OTEL_ENABLED`, авто-инструментация (zero-code, где можно), поля корреляции
переиспользуют уже стандартизованный для Langfuse набор `tenant_id / user_id / stage / request_id`
([архитектура §6](/architecture.md), [CLAUDE.md](/CLAUDE.md) «Соглашения → LLM»).

### 4.1. Python — api / worker / beat

- Зависимости (в `services/api/pyproject.toml`, опциональная группа `otel`): `opentelemetry-distro`,
  `opentelemetry-exporter-otlp`, авто-инструментации `fastapi`, `httpx`, `celery`, `redis`, `sqlalchemy`/`psycopg`,
  `logging`.
- Запуск через враппер `opentelemetry-instrument` перед `uvicorn` / `celery` (правим `command` в compose и Dockerfile
  entrypoint). При `OTEL_ENABLED=false` враппер — no-op (не задаём OTLP endpoint → SDK молчит).
- Структурные логи: перевести stdlib `logging` на JSON (`structlog` или `python-json-logger`) с автоинъекцией
  `trace_id`/`span_id` из активного спана. Единый форматтер в `app/observability.py`.
- Корреляция полей: FastAPI-middleware кладёт `request_id` (входящий заголовок или генерит), `tenant_id`, `user_id`,
  `stage` в contextvars → форматтер логов и атрибуты спана берут оттуда. Тот же contextvar уже нужен для тегов Langfuse
  — переиспользуем, не плодим.
- Celery: `CeleryInstrumentor` пробрасывает trace-контекст через заголовки задачи → цепочка
  `HTTP-запрос → enqueue → worker (fetch/extract/score/generate)` собирается в **один трейс** (стадии из
  [плана M1](/m1-ingestion-plan.md), очереди `fetch,extract,score,generate,emails`).

### 4.2. Node — web (Next.js 15 App Router)

- `@vercel/otel` (нативная интеграция с App Router через `instrumentation.ts` register-hook) либо
  `@opentelemetry/sdk-node` + `auto-instrumentations-node`. Рекомендуем `@vercel/otel` — минимум кода.
- Структурные логи: `pino` в stdout (JSON), инъекция `trace_id`.
- **Проброс контекста web → api.** В существующей fetch-обёртке `apps/web/.../internal.ts` (ходит в api по
  `http://api:8000`) инжектим W3C `traceparent` + `x-request-id`. Так трейс не рвётся на границе сервисов.

### 4.3. Traefik

- Включить `accesslog` в JSON, ротация json-file. Collector `filelog` его тоже подхватывает.
- Отбрасывать шум health-проб (`/api/health`, `/ready`, `/api/health` web) processor'ом `filter` в Collector, чтобы не
  засорять хранилище.

## 5. Конфигурация Collector и VictoriaLogs

**OTel Collector (`otelcol-contrib`)** — pipeline:

- receivers: `filelog` (docker container logs + Traefik), `otlp` (grpc/http — под трейсы/метрики фаз B/C).
- processors:
  - `resourcedetection` / `resource` — проставить `service.namespace=<env>`, `deployment.environment`;
  - `transform` + `redact/attributes` — **вырезать PII/секреты**: `authorization`, `cookie`, `set-cookie`,
    e-mail'ы, тела с контентом статей по allow-list полей;
  - `filter` — дропнуть health-пробы и debug-шум;
  - `batch`, `memory_limiter` — держать RAM в узде.
- exporters: `otlphttp` → VictoriaLogs (`/insert/opentelemetry/v1/logs`). (Фазы B/C: трейсы → **VictoriaTraces**,
  метрики → VictoriaMetrics — единая экосистема Victoria*.)

**VictoriaLogs:**

- `-retentionPeriod=14d` (стартуем с 7–14 дней), жёсткий потолок диска `-retention.maxDiskSpaceUsageBytes`.
- Индексируемые поля (stream fields): `service.name`, `env`, `tenant_id` — по ним фильтруем в LogsQL.
- Данные в именованный volume, бэкап не нужен (наблюдаемость — не source of truth).

**Ресурсы (mem_limit):** VictoriaLogs `256m`, Collector `128m`. Итог ≤ ~400 MB — вписывается в ~6 GB свободных
([деплой §13](/deployment.md)). Параметризовать через `.env` как остальные лимиты.

## 6. Изменения в репозитории (декомпозиция)

| # | Где | Что |
|---|---|---|
| T1 | `deploy/observability/compose.yml` (новый) | Стек `otel-collector` + `victorialogs`, сеть `obs` (external), volume VL, Traefik-лейблы на UI VL + basic-auth middleware. |
| T2 | `deploy/observability/otelcol.yaml`, `victorialogs` флаги | Конфиг Collector (receivers/processors/exporters) и retention/диск VL. |
| T3 | `deploy/compose.yml` | Подключить web/api/worker/beat к сети `obs`; ограничить `logging.driver=json-file` (`max-size`,`max-file`); прокинуть `OTEL_*` env. |
| T4 | `deploy/env.example` | `OTEL_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_RESOURCE_ATTRIBUTES`, `OTEL_TRACES_SAMPLER*`, лимиты RAM, basic-auth VL. |
| T5 | `services/api/pyproject.toml` | Опц. группа `otel`; Dockerfile entrypoint через `opentelemetry-instrument` под флагом. |
| T6 | `services/api/app/observability.py` (новый) | JSON-логгер + contextvars (`request_id/tenant_id/user_id/stage`), FastAPI-middleware, инициализация SDK. |
| T7 | `apps/web/instrumentation.ts` + `internal.ts` | `@vercel/otel` register; `pino` JSON-логи; инжект `traceparent`/`x-request-id` в вызовы api. |
| T8 | Traefik (`deploy/traefik/`) | Включить JSON access-log. |
| T9 | `docs/deployment.md` | Новый раздел «Наблюдаемость» + снять строку «Метрики/алерты» из §12 роадмапа (→ ссылка на этот план). |
| T10 | CI (`.github/workflows/ci.yml`) | Smoke-тест: приложение стартует и с `OTEL_ENABLED=true`, и с `=false`; линт конфигов. |

## 7. Фазы внедрения

- **Фаза A — Логи (MVP наблюдаемости).** T1–T4, T6 (JSON-логи + поля корреляции), T7 (только pino+request_id), T8–T10.
  Выходной критерий — §1.1–§1.6. Трейсы/метрики ещё выключены (`OTEL_TRACES_SAMPLER=always_off`).
- **Фаза B — Трейсы.** Включить авто-инструментацию (FastAPI/httpx/Celery/SQLAlchemy/Redis + Node SDK), проброс
  `traceparent`, экспорт спанов в Collector → **VictoriaTraces** (единая экосистема Victoria*). Хвостовое семплирование
  (`tail_sampling` в Collector: 100% ошибок + N% успешных). Кода приложения почти не касается — включение конфигом.
- **Фаза C — Метрики + алерты.** OTel/инфра-метрики → VictoriaMetrics; `vmalert`/Alertmanager: очереди Celery растут,
  api 5xx, латентность, диск/RAM VM, застрявшие тенанты в конвейере. Закрывает остаток строки §12 роадмапа.

Фаза A — целевая для этого плана; B и C — заложены, включаются по потребности.

## 8. Безопасность и приватность

- Логи содержат тенант-данные (контент статей, e-mail'ы). **PII-редакция** в Collector (`redact`/`transform`) до записи;
  секреты/заголовки авторизации вырезаются всегда.
- UI VictoriaLogs — за Traefik + basic-auth (+ опц. IP-allowlist), это внутренний ops-инструмент, не мультитенантный
  UI. Наружу торчит только он; сам VL и Collector — в `obs`, без host-портов.
- Короткая retention (7–14 дней) минимизирует объём хранимого PII.
- Изоляция тенантов в самих данных ([ADR-0002](/adr/0002-tenant-isolation-postgres-rls.md)) наблюдаемости не касается —
  доступ к логам только у операторов.

## 9. Связь с Langfuse (не дублируем)

| | Langfuse ([ADR-0004](/adr/0004-litellm-gateway-langfuse-metering.md)) | OTel + VictoriaLogs (этот план) |
|---|---|---|
| Домен | LLM: стоимость $ per tenant, качество промптов, трейсы генерации | Приложение/инфра: логи, латентность, ошибки, поток запроса |
| Вопрос | «сколько сжёг тенант / что попросили у модели» | «почему запрос упал / где узкое место конвейера» |
| Статус | roadmap, в MVP off | этот план, фаза A — near-term |

**Мост.** `request_id` кладём и в OTel-спан, и в metadata Langfuse-трейса → из строки лога находим соответствующий
LLM-трейс и наоборот. Дублирования нет: cost-metering остаётся за Langfuse, app-телеметрия — за OTel.

## 10. Риски и решения

1. **RAM тесной VM.** → Фаза A = только логи; жёсткие `mem_limit`; VictoriaLogs вместо Loki/ELK; трейсы с хвостовым
   семплированием позже.
2. **Рост диска от логов.** → retention + `maxDiskSpaceUsageBytes` в VL; `json-file` ротация в docker; дроп health-проб.
3. **Collector как SPOF.** → логи через scrape json-file (переживают даунтайм Collector); трейсы — best-effort, не
   критичны для разбора инцидентов.
4. **Связанность с приложением.** → всё за `OTEL_ENABLED`, авто-инструментация zero-code, kill-switch без пересборки.
5. **Кардинальность `tenant_id`.** → в **логах** VictoriaLogs высокая кардинальность полей штатна; в **метриках** (фаза C)
   `tenant_id` меткой НЕ делаем — только агрегаты, тенант-разрез остаётся за Langfuse/Postgres `ai_usage`.
6. **Утечка PII в логи.** → redact-processor + allow-list полей + короткая retention (§8).

## 11. Решённые вопросы

- **PR-окружения (когда появятся) — тот же общий стек наблюдаемости, вариант A.** Ephemeral-окружения на каждый PR
  ([деплой §12](/deployment.md), пока в роадмапе) пишут в **один общий** VictoriaLogs/VictoriaTraces с меткой
  `env=pr-<n>`, свой Collector/VL на PR не поднимаем — на тесной VM (2 vCPU / 8 GB) это дорого. Условия жизнеспособности:
  короткая retention для `pr-*` (данные умирают вскоре после закрытия PR), чистка по метке при сносе окружения, и
  контроль, чтобы «шумный» PR не забил диск, общий с продом (`maxDiskSpaceUsageBytes` из §5). Вернёмся к изоляции
  (вариант B — отдельный мини-стек на PR), только если общий стек начнёт мешать проду.
- **Бэкенд трейсов (фаза B) — VictoriaTraces.** Единая экосистема Victoria* (тот же оператор/UI-стиль, что VictoriaLogs
  и VictoriaMetrics фазы C), лёгкий, нативный OTLP-приём. Не тащим отдельный Jaeger/Tempo — меньше компонентов на
  тесной VM и один язык запросов/эксплуатации на весь стек наблюдаемости.
- **Grafana не ставим** — хватает нативного UI VictoriaLogs (LogsQL) для логов; на фазе C дашборды метрик — нативным
  UI VictoriaMetrics (vmui). Отдельный Grafana поверх VL/VM не заводим (лишний компонент на тесной VM); вернёмся к
  вопросу, только если появится потребность в сводных кросс-сигнальных дашбордах.
