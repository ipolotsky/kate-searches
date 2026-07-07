-- KateSearches — веха M5.1 (строгий hard-cap скоринга и генерации). Аддитивно поверх 0005, идемпотентно.
-- Атомарный per-tenant счётчик расхода для энфорса бюджета (reserve -> call -> settle). Ключ по
-- периоду 'YYYY-MM' (UTC) даёт бесплатный месячный сброс. ai_usage остаётся для отчётов/апселла
-- (per-stage), этот леджер — только для энфорса (service_role/пайплайн пишет, web не читает).

create table if not exists tenant_budget_ledger (
  tenant_id  uuid not null references tenants(id) on delete cascade,
  period     text not null,                       -- 'YYYY-MM' в UTC
  spent_usd  numeric not null default 0,           -- зарезервировано + сверено с фактом
  updated_at timestamptz not null default now(),
  primary key (tenant_id, period)
);

alter table tenant_budget_ledger enable row level security;

-- Control/enforcement-таблица: authenticated не читает и не пишет (энфорс идёт под service_role,
-- отчёты для owner берутся из ai_usage). Дисциплина: явный revoke all, политик для authenticated нет.
revoke all on tenant_budget_ledger from authenticated;
