---
type: ADR
title: "ADR-0002 — Изоляция тенантов через Postgres RLS (Supabase)"
description: Мультитенантность обеспечивается row-level security в БД, а не authz в коде.
status: accepted
tags: [adr, architecture, security, multitenancy]
generated:
  by: human:alexander.polyakov
  at: 2026-08-01
---

# ADR-0002 — Изоляция тенантов через Postgres RLS (Supabase)

**Статус:** accepted · **Дата решения:** 2026-06-30.

В контексте B2B-SaaS с данными многих клиентов в одной общей БД,
сталкиваясь с требованием строгой изоляции тенантов при минимуме ручной авторизации,
мы выбрали **Supabase Postgres + RLS-политику `tenant_id = auth.jwt() ->> 'tenant_id'`** на каждой таблице,
и отвергли authz в коде приложения (легко ошибиться, дублируется в каждом запросе) и отдельную БД на тенанта (дорого и сложно для MVP),
чтобы описать авторизацию один раз в SQL и авто-скоупить любой запрос,
принимая как компромисс завязку на Supabase/Postgres, дисциплину «каждая таблица с `tenant_id` + политикой» и аудируемый обход через service role для админки.

Детали схемы и политик — [архитектура §5](/architecture.md) и [§8](/architecture.md).
