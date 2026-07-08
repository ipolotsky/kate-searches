-- KateSearches — веха M6.1 (надёжность расхода/пайплайна). Строго аддитивно поверх 0006, идемпотентно.
-- (1) Промежуточный claim-статус 'scoring' — pre-LLM claim скоринга (симметрично 'drafting' у генерации),
--     чтобы конкурентные прогоны одного run_id (напр. re-dispatch «медленного, но живого» прогона)
--     не скорили одну статью дважды: двойной LLM-спенд и двойной резерв.
-- (2) status_changed_at — момент входа в claim-статус, для reaper застрявших 'scoring'/'drafting'
--     (краш воркера между claim и разрешением статуса), чтобы статья не осталась в limbo навсегда.

alter table articles drop constraint if exists articles_status_check;
alter table articles add constraint articles_status_check
  check (status in (
    'new','extracted','filtered_out','scored','scoring','drafting','drafted','duplicate'
  ));

alter table articles add column if not exists status_changed_at timestamptz;

-- Частичный индекс под reaper: выбираем только застрявшие в claim-статусах.
create index if not exists idx_articles_claimed
  on articles(status, status_changed_at)
  where status in ('scoring', 'drafting');
