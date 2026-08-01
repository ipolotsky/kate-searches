---
type: ADR
title: "ADR-0001 — Два сервиса: Next.js (web) + FastAPI (AI/скрапинг)"
description: Раздельные web- и AI-сервисы вместо монолита или микросервисного зоопарка.
status: accepted
tags: [adr, architecture, stack]
generated:
  by: human:alexander.polyakov
  at: 2026-08-01
---

# ADR-0001 — Два сервиса: Next.js (web) + FastAPI (AI/скрапинг)

**Статус:** accepted · **Дата решения:** 2026-06-30 · заменяет `D1` из decision log.

В контексте B2B-SaaS, где UI живёт в экосистеме Node, а скрапинг и LLM-тулинг — в Python,
сталкиваясь с необходимостью одновременно и богатого React-UI (куплен Flowbite Pro), и зрелых Python-либ (Crawl4AI, trafilatura, Instructor, dlt),
мы выбрали **два раздельных сервиса** — Next.js 15 (App Router) как UI + тонкий BFF и FastAPI как «мозг» (ingestion / scoring / generation / metering),
и отвергли монолит на одном Next.js (LLM/скрапинг-тулинг в Node незрелый) и микросервисный зоопарк (избыточно для команды из 1–2 инженеров),
чтобы получить чёткую границу ответственности и использовать сильные стороны каждой экосистемы,
принимая как компромисс сетевую границу web↔api (внутренний API-контракт + ретрай в `internal.ts`) и две отдельные сборки/деплоя.

Детали стека и границы — [архитектура §1](/architecture.md).
