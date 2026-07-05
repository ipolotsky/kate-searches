-- KateSearches — веха M2 (скоринг). Строго аддитивно поверх 0002, идемпотентно.
-- Счётчики стадии score в леджере прогонов. Новых таблиц и RLS-политик нет.

-- ─────────────────────────────────────────── pipeline_runs: счётчики стадии score
alter table pipeline_runs add column if not exists scored int not null default 0;
alter table pipeline_runs add column if not exists filtered_out int not null default 0;
