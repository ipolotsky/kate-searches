---
okf_version: "0.2"
---

# ADR — Архитектурные решения (Y-Statement)

Записи архитектурных и продуктовых решений KateSearches в формате
[Y-Statement](https://medium.com/olzzio/y-statements-10eb07b5a177) (контекст → развилка →
выбор → отвергнутое → выгода → компромисс). Перенесены из decision log в
[обзоре](/overview.md). Родительский листинг — [index.md](/index.md).

- [ADR-0001 — Два сервиса: Next.js + FastAPI](0001-split-web-api-services.md)
- [ADR-0002 — Изоляция тенантов через Postgres RLS](0002-tenant-isolation-postgres-rls.md)
- [ADR-0003 — LLM-оркестрация без LangChain](0003-no-langchain-instructor-linear-dag.md)
- [ADR-0004 — Гейтвей LiteLLM + метеринг Langfuse](0004-litellm-gateway-langfuse-metering.md)
- [ADR-0005 — Источники MVP: RSS + sitemap + Crawl4AI](0005-mvp-sources-rss-sitemap-crawl4ai.md)
- [ADR-0006 — Генерация: симбиоз «инфоповод × бренд», без SKU](0006-generation-brand-symbiosis-no-sku.md)
- [ADR-0007 — Скоуп MVP: полноценный self-serve мультитенант](0007-mvp-full-selfserve-multitenant.md)
- [ADR-0008 — Биллинга нет в MVP, только cost-metering](0008-no-billing-mvp-cost-metering.md)
- [ADR-0009 — Юрисдикция: глобально / не-РФ](0009-jurisdiction-global-non-ru.md)
- [ADR-0010 — Наблюдаемость: OpenTelemetry + VictoriaLogs](0010-observability-otel-victorialogs.md)
