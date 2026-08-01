---
okf_version: "0.2"
---

# Планы и статус

Планы вех, запуска и снимок состояния проекта KateSearches. Родительский листинг —
[index.md](/index.md).

* [План вехи M1 — Ingestion](m1-ingestion-plan.md) — контракт адаптера, оркестрация Celery, дедуп/новизна, декомпозиция T1–T15.
* [План запуска](launch-plan.md) — ревью кодовой базы, механика триала, биллинг, уведомления, launch-блокеры.
* [Handoff — снимок состояния проекта](handoff.md) — что готово и развёрнуто, что нужно от владельца, как запускать; лог вех M0–M6.4.
* [План — Наблюдаемость: OpenTelemetry + VictoriaLogs](observability-otel-victorialogs-plan.md) — централизованные логи/трейсы/метрики на VM; фазы A (логи) → B (трейсы) → C (метрики/алерты). См. [ADR-0010](/adr/0010-observability-otel-victorialogs.md).
