---
type: ADR
title: "ADR-0005 — Источники MVP: RSS + news-sitemap + Crawl4AI"
description: Ingestion в MVP через RSS/sitemap/Crawl4AI за единым адаптер-контрактом; соцсети — фаза 2.
status: accepted
tags: [adr, architecture, ingestion]
generated:
  by: human:alexander.polyakov
  at: 2026-08-01
---

# ADR-0005 — Источники MVP: RSS + news-sitemap + Crawl4AI

**Статус:** accepted · **Дата решения:** 2026-06-30.

В контексте ежедневного ingestion новостей в нише клиента,
сталкиваясь с задачей покрыть большинство источников дёшево и оставить путь к соцсетям,
мы выбрали **RSS + news-sitemap + Crawl4AI-скрапер** (Firecrawl fallback, Bright Data/Zyte при анти-боте) за единым контрактом `SourceAdapter`,
и отвергли тяжёлый ingestion-стек (Airbyte / Kafka / NiFi — рано) и соцсеть-адаптеры в MVP (Telegram/Reddit — фаза 2, но абстракция готова с D1),
чтобы получить дешёвый каскад дорого→дёшево, единый пайплайн ниже ingestion и расширяемость без переписывания,
принимая как компромисс, что соцсети недоступны в MVP, а анти-бот-источники требуют платных апстримов.

Контракт адаптера — [архитектура §4](/architecture.md); скоуп — [MVP-спека §2](/mvp-spec.md); план — [M1](/plans/m1-ingestion-plan.md).
