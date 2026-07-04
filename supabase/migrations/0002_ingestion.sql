-- KateSearches — веха M1 (ingestion). Строго аддитивно поверх 0001, идемпотентно.
-- Новые control-таблицы (pipeline_runs, source_secrets) — не писабельны authenticated.

-- ─────────────────────────────────────────── articles: метаданные, дедуп-линковка, атрибуция прогона
alter table articles add column if not exists metadata jsonb not null default '{}'::jsonb;
alter table articles add column if not exists duplicate_of uuid references articles(id) on delete set null;
alter table articles add column if not exists last_pipeline_run_id uuid;
alter table articles drop constraint if exists articles_status_check;
alter table articles add constraint articles_status_check
  check (status in ('new','extracted','filtered_out','scored','drafted','duplicate'));
create index if not exists idx_articles_content_hash on articles(tenant_id, content_hash);

-- ─────────────────────────────────────────── sources: здоровье + хук per-source cadence
alter table sources add column if not exists last_status text;
alter table sources add column if not exists last_error text;
alter table sources add column if not exists last_error_at timestamptz;
alter table sources add column if not exists next_run_at timestamptz;

-- ─────────────────────────────────────────── tenants: локальный час дневного прогона для tz-диспетчера
alter table tenants add column if not exists pipeline_hour_local smallint not null default 6;

-- ─────────────────────────────────────────── ai_usage: атрибуция стоимости к прогону
alter table ai_usage add column if not exists pipeline_run_id uuid;

-- ─────────────────────────────────────────── мультиисточниковая провенансность
create table if not exists article_sources (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  article_id uuid not null references articles(id) on delete cascade,
  source_id uuid references sources(id) on delete set null,
  external_id text,
  priority_at_seen int,
  first_seen_at timestamptz not null default now(),
  unique (article_id, source_id)
);
create index if not exists idx_article_sources_tenant on article_sources(tenant_id, source_id);

-- ─────────────────────────────────────────── леджер прогонов: идемпотентный диспатч + наблюдаемость
create table if not exists pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  run_date date not null,
  mode text not null default 'incremental' check (mode in ('incremental','backfill')),
  status text not null default 'running' check (status in ('running','success','partial','failed')),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  fetched int not null default 0,
  new int not null default 0,
  duplicated int not null default 0,
  extracted int not null default 0,
  failed int not null default 0,
  stats jsonb not null default '{}'::jsonb,
  unique (tenant_id, run_date, mode)
);
create index if not exists idx_pipeline_runs_tenant on pipeline_runs(tenant_id, run_date desc);

-- ─────────────────────────────────────────── секреты источников: service_role-only (OAuth/токены фаз 2/3)
create table if not exists source_secrets (
  source_id uuid primary key references sources(id) on delete cascade,
  tenant_id uuid not null references tenants(id) on delete cascade,
  secrets jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- ─────────────────────────────────────────── RLS
alter table article_sources enable row level security;
alter table pipeline_runs enable row level security;
alter table source_secrets enable row level security;

drop policy if exists article_sources_isolation on article_sources;
drop policy if exists article_sources_select on article_sources;
create policy article_sources_select on article_sources
  for select using (tenant_id = current_tenant_id());

drop policy if exists pipeline_runs_isolation on pipeline_runs;
drop policy if exists pipeline_runs_select on pipeline_runs;
create policy pipeline_runs_select on pipeline_runs
  for select using (tenant_id = current_tenant_id());

-- source_secrets: политик для authenticated нет => доступа к строкам нет; service_role обходит RLS.

-- ─────────────────────────────────────────── гранты: ужесточаем control-таблицы
-- Supabase дефолтно грантит authenticated ВСЕ привилегии на новые таблицы, включая
-- TRUNCATE/REFERENCES/TRIGGER. TRUNCATE обходит RLS и сносит данные всех тенантов —
-- поэтому для control-таблиц revoke ALL, а чтение возвращаем явным grant select.
-- article_sources/pipeline_runs — read-only леджер и провенанс (пишет пайплайн под service_role).
revoke all on article_sources from authenticated;
grant select on article_sources to authenticated;
revoke all on pipeline_runs from authenticated;
grant select on pipeline_runs to authenticated;
-- source_secrets — полностью скрыто от authenticated (OAuth/токены).
revoke all on source_secrets from authenticated;

-- Закрываем ту же TRUNCATE-дыру на control-таблицах M0 (в 0001 сняли только insert/update/delete).
revoke all on tenants from authenticated;
grant select on tenants to authenticated;
revoke all on users from authenticated;
grant select on users to authenticated;
revoke all on ai_usage from authenticated;
grant select on ai_usage to authenticated;

-- Content-таблицы: authenticated сохраняет RLS-скоупленный CRUD, но НЕ TRUNCATE (обходит RLS
-- и сносит строки всех тенантов). Defense-in-depth: PostgREST не отдаёт TRUNCATE, роль NOLOGIN.
revoke truncate on brand_profiles, sources, articles, posts, feedback from authenticated;
