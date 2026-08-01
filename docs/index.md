---
okf_version: "0.2"
---

# KateSearches — база знаний (OKF bundle)

Продуктовые и технические артефакты проекта KateSearches в формате
[OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) v0.2.
История изменений — [log.md](log.md). Проверка здоровья базы — скилл `/okf-audit`.

## Обзор и продукт

* [Обзор и decision log](overview.md) — что за продукт, зафиксированные решения, порядок чтения, глоссарий.
* [PRD / Продуктовая упаковка](prd.md) — проблема, ICP, JTBD, позиционирование, фичи, метрики, монетизация, риски.
* [Рыночный и технический ресёрч](market-research.md) — конкуренты, white space, бенчмарки цен, выводы по ingestion / AI / SaaS-стеку.
* [Юнит-экономика и тарифная сетка](pricing-unit-economics.md) — COGS, тарифная сетка, точка прибыльности, логика апселла.

## Решения (ADR)

* [Архитектурные решения (ADR)](adr/index.md) — decision log в формате Y-Statement: стек и раздельные сервисы, изоляция тенантов через RLS, LLM-оркестрация без LangChain, гейтвей+метеринг, источники, генерация-симбиоз, скоуп/биллинг/юрисдикция.

## Технические спеки

* [Техническая архитектура](architecture.md) — стек, схема данных, изоляция тенантов (RLS), адаптеры источников, AI-пайплайн, cost-metering, инфра.
* [AI-пайплайн и промпт-спеки](ai-pipeline-prompts.md) — полный порядок стадий (ingest→extract→dedup→score→generate→feedback), рубрика скоринга (критерии отбора), генерация-симбиоз «инфоповод × бренд» (без SKU), гейтвей LiteLLM + метеринг Langfuse + роутинг моделей по стадии, промпт-шаблоны, JSON-схемы, SEO/AEO-чеклист.
* [MVP-спецификация](mvp-spec.md) — скоуп MVP, источники MVP (RSS/sitemap/Crawl4AI), user stories, экраны, статусы постов, acceptance criteria, вехи.
* [Спек деплоя и инфраструктуры](deployment.md) — CI/CD, Docker, Traefik, VM, прод и staging.

## Планы и статус

Раздел [Планы и статус](plans/index.md):

* [План вехи M1 — Ingestion](plans/m1-ingestion-plan.md) — контракт адаптера, оркестрация Celery, дедуп/новизна, декомпозиция T1–T15.
* [План запуска](plans/launch-plan.md) — ревью кодовой базы, механика триала, биллинг, уведомления, launch-блокеры.
* [Handoff — снимок состояния проекта](plans/handoff.md) — что готово и развёрнуто, что нужно от владельца, как запускать; лог вех M0–M6.4.
