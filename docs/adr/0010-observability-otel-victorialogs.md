---
type: ADR
title: "ADR-0010 — Наблюдаемость: OpenTelemetry + VictoriaLogs"
description: Единая OTel-инструментация приложения и лёгкий бэкенд логов VictoriaLogs на VM; отдельно от LLM-метеринга Langfuse.
status: accepted
tags: [adr, architecture, observability, deployment]
generated:
  by: human:alexander.polyakov
  at: 2026-08-01
---

# ADR-0010 — Наблюдаемость: OpenTelemetry + VictoriaLogs

**Статус:** accepted · **Дата решения:** 2026-08-01.

В контексте того, что единственный инструмент наблюдения в проде — эфемерный `docker compose logs` без истории,
корреляции между `web → api → worker` и поиска по `tenant_id`/`request_id` ([деплой §10](/deployment.md)),
а строка «Метрики/алерты» висит в [инфра-роадмапе §12](/deployment.md),
сталкиваясь с необходимостью централизованных логов/трейсов/метрик на тесной VM (2 vCPU / 8 GB, два app-стека + Traefik)
без тяжёлого JVM-стека и без вендор-лока,
мы выбрали **OpenTelemetry** как единый шов инструментации (инструментируем раз, бэкенд меняем конфигом Collector)
плюс **VictoriaLogs** как лёгкий бэкенд логов (один бинарь, без внешних зависимостей, ~десятки MB RAM, нативный OTLP-приём),
и отвергли ELK/OpenSearch (гигабайты RAM, не влезает), Loki (тяжелее и капризнее VL по кардинальности)
и push-доставку логов из приложения (хрупко: даунтайм Collector = потеря логов) — логи забираем scrape'ом из docker json-file,
чтобы получить переживающие `rollout` централизованные логи с корреляцией по `trace_id/request_id/tenant_id`, общий стек на оба
окружения (разделение меткой `env`) и путь к трейсам/метрикам без правок кода приложения,
принимая как компромисс ещё два self-hosted компонента на VM (Collector + VictoriaLogs, ≤ ~400 MB RAM) и то, что трейсы
(фаза B) и метрики/алерты (фаза C) включаются позже — в near-term скоупе только логи (фаза A).

Комплементарно, не заменяет **Langfuse** ([ADR-0004](0004-litellm-gateway-langfuse-metering.md)): тот считает LLM-стоимость
per tenant, OTel+VictoriaLogs — телеметрию приложения/инфры; мост между контурами — общий `request_id`.
План внедрения и декомпозиция — [observability-otel-victorialogs-plan](/plans/observability-otel-victorialogs-plan.md).
