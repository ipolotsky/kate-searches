-- KateSearches — веха M5 (метеринг/бюджет/апселл + админка). Строго аддитивно поверх 0004, идемпотентно.
-- Новая control-таблица platform_admins (глобальные админы) + агрегационные RPC для расхода.
-- Схема бюджета уже есть с 0001 (tenants.plan/ai_budget_usd_month/upsell_threshold_pct);
-- ничего в tenants не меняем. Расход считаем compute-on-read из ai_usage (индекс idx_ai_usage_tenant_time
-- покрывает и owner-, и hard-cap-запрос). ai_spent_usd_month остаётся derived/мёртвой колонкой.

-- ─────────────────────────────────────────── platform_admins: глобальные (кросс-тенант) админы
-- Отдельная таблица, а не пофтенантная users.role='admin' (та скоупится тенантом; глобальный
-- админ — отдельный аудируемый путь через service_role). Сидинг — только под service_role.
create table if not exists platform_admins (
  user_id    uuid primary key references users(id) on delete cascade,
  created_at timestamptz not null default now()
);
alter table platform_admins enable row level security;

-- Юзер видит ТОЛЬКО свою строку — этого достаточно, чтобы проверить «я админ?» на сервере
-- под обычным authenticated-клиентом, без service_role. Список всех админов — не отдаётся.
drop policy if exists platform_admins_self on platform_admins;
create policy platform_admins_self on platform_admins
  for select using (user_id = auth.uid());

-- Дисциплина control-таблиц (см. HANDOFF §follow-ups): явный revoke all + узкий grant select.
-- Запись/сидинг только под service_role (обходит RLS).
revoke all on platform_admins from authenticated;
grant select on platform_admins to authenticated;

-- ─────────────────────────────────────────── RPC агрегации расхода
-- PostgREST по умолчанию не даёт sum() в .select(), а [api] max_rows=1000 обрезал бы client-side
-- сумму строк — поэтому агрегируем на стороне БД. now() на Supabase в UTC, date_trunc('month', now())
-- = UTC-начало месяца, совпадает с бэкенд-хелпером month_start_utc().

-- Расход текущего тенанта за календарный месяц. security invoker => RLS ai_usage применяется
-- (current_tenant_id() резолвит tenant по auth.uid()). Для owner-тотала и плашки в layout.
create or replace function tenant_month_spend() returns numeric
language sql
stable
security invoker
set search_path = public
as $$
  select coalesce(sum(cost_usd), 0)
  from ai_usage
  where tenant_id = current_tenant_id()
    and created_at >= date_trunc('month', now());
$$;

revoke execute on function tenant_month_spend() from public;
grant execute on function tenant_month_spend() to authenticated;

-- Разбивка расхода текущего тенанта по стадиям за месяц (score/draft/extract/other).
create or replace function tenant_month_usage_by_stage()
returns table(stage text, cost_usd numeric, calls bigint)
language sql
stable
security invoker
set search_path = public
as $$
  select stage, coalesce(sum(cost_usd), 0) as cost_usd, count(*) as calls
  from ai_usage
  where tenant_id = current_tenant_id()
    and created_at >= date_trunc('month', now())
  group by stage;
$$;

revoke execute on function tenant_month_usage_by_stage() from public;
grant execute on function tenant_month_usage_by_stage() to authenticated;

-- Отчёт по всем тенантам (админка). security definer => обходит RLS, поэтому execute ТОЛЬКО
-- service_role (иначе тенант увидел бы всех). Зовётся из web под createAdminClient().
create or replace function admin_tenant_report(p_since timestamptz)
returns table(
  tenant_id uuid,
  name text,
  plan text,
  ai_budget_usd_month numeric,
  upsell_threshold_pct int,
  spend_month numeric,
  drafts_month bigint,
  users_count bigint,
  created_at timestamptz
)
language sql
stable
security definer
set search_path = public
as $$
  select
    t.id,
    t.name,
    t.plan,
    t.ai_budget_usd_month,
    t.upsell_threshold_pct,
    coalesce(u.spend, 0) as spend_month,
    coalesce(p.drafts, 0) as drafts_month,
    coalesce(m.members, 0) as users_count,
    t.created_at
  from tenants t
  left join (
    select tenant_id, sum(cost_usd) as spend
    from ai_usage where created_at >= p_since group by tenant_id
  ) u on u.tenant_id = t.id
  left join (
    select tenant_id, count(*) as drafts
    from posts where created_at >= p_since group by tenant_id
  ) p on p.tenant_id = t.id
  left join (
    select tenant_id, count(*) as members
    from users group by tenant_id
  ) m on m.tenant_id = t.id
  order by t.created_at desc;
$$;

-- ВАЖНО: revoke от public, а не только anon/authenticated. У функций есть дефолтный EXECUTE
-- для PUBLIC; revoke конкретных ролей его НЕ снимает (роли наследуют execute через PUBLIC),
-- иначе security-definer обходит RLS и authenticated-тенант читает кросс-тенант данные всех.
revoke execute on function admin_tenant_report(timestamptz) from public;
grant execute on function admin_tenant_report(timestamptz) to service_role;

-- Разбивка расхода конкретного тенанта по стадиям (карточка тенанта в админке). security definer
-- => execute только service_role. Через БД-агрегацию, чтобы не упереться в max_rows при выборке строк.
create or replace function admin_tenant_usage_by_stage(p_tenant_id uuid, p_since timestamptz)
returns table(stage text, cost_usd numeric, calls bigint)
language sql
stable
security definer
set search_path = public
as $$
  select stage, coalesce(sum(cost_usd), 0) as cost_usd, count(*) as calls
  from ai_usage
  where tenant_id = p_tenant_id
    and created_at >= p_since
  group by stage;
$$;

-- См. примечание выше: revoke от public обязателен, чтобы definer не был вызываем тенантом.
revoke execute on function admin_tenant_usage_by_stage(uuid, timestamptz) from public;
grant execute on function admin_tenant_usage_by_stage(uuid, timestamptz) to service_role;
