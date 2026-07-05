-- KateSearches — веха M3 (генерация черновиков). Строго аддитивно поверх 0003, идемпотентно.
-- Счётчик стадии draft в леджере прогонов + промежуточный claim-статус 'drafting'.
-- Новых таблиц и RLS-политик нет: posts и его RLS есть с 0001.

-- ─────────────────────────────────────────── pipeline_runs: счётчик стадии draft
alter table pipeline_runs add column if not exists drafted int not null default 0;

-- ─────────────────────────────────────────── articles: claim-статус 'drafting'
-- Атомарный claim scored -> drafting ДО дорогого LLM-вызова не даёт конкурентным
-- on-demand генерациям дублировать спенд сильной модели на одну статью.
alter table articles drop constraint if exists articles_status_check;
alter table articles add constraint articles_status_check
  check (status in ('new','extracted','filtered_out','scored','drafting','drafted','duplicate'));
