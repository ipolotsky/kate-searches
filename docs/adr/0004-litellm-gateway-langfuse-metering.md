---
type: ADR
title: "ADR-0004 — Гейтвей LiteLLM + метеринг Langfuse"
description: Per-tenant бюджеты и роутинг через LiteLLM, cost-metering через Langfuse.
status: accepted
tags: [adr, architecture, ai, cost-metering]
generated:
  by: human:alexander.polyakov
  at: 2026-08-01
---

# ADR-0004 — Гейтвей LiteLLM + метеринг Langfuse

**Статус:** accepted · **Дата решения:** 2026-06-30.

В контексте мультипровайдерных LLM-вызовов (OpenAI / Anthropic / Gemini) с per-tenant бюджетами и учётом стоимости,
сталкиваясь с необходимостью hard-бюджета на тенанта, роутинга моделей по стадии и точного cost-metering без наценки,
мы выбрали **self-hosted LiteLLM** (virtual keys, hard-бюджет, роутинг score→cheap / draft→strong) плюс **self-hosted Langfuse** (cost per tenant),
и отвергли платный гейтвей-провайдер с +5% маркапом и прямой SDK без гейтвея (нет бюджет-капа и единого метеринга),
чтобы получить рантайм-кэп маржи per-tenant, единый роутинг и источник правды по $,
принимая как компромисс эксплуатацию двух self-hosted компонентов — в MVP-проде они пока выключены (прямой SDK, `LANGFUSE_ENABLED=false`), включение — на роадмапе.

Контур cost-metering — [архитектура §6](/architecture.md); статус в проде — [деплой §12](/deployment.md).
