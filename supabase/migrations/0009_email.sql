-- KateSearches — веха M6.3 (email-уведомления, Resend). Аддитивно поверх 0008, идемпотентно.
-- Слать всё из Python/Celery. Три таблицы: предпочтения (per-type тумблеры + токен отписки),
-- suppression (bounce/complaint из вебхуков, pre-send фильтр) и dispatch_log (идемпотентность +
-- аудит: уникальный (user_id, notification_type, dedup_key) не даёт дублей на ретрае Celery).

-- ─────────────────────────────────────────── email_preferences: per-type согласие + токен отписки
create table if not exists email_preferences (
  user_id                 uuid primary key references users(id) on delete cascade,
  tenant_id               uuid not null references tenants(id) on delete cascade,
  digest_enabled          boolean not null default true,
  product_updates_enabled boolean not null default true,
  unsubscribe_token       uuid not null default gen_random_uuid() unique,
  consent_source          text,
  consent_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now()
);
alter table email_preferences enable row level security;

-- Юзер видит и меняет ТОЛЬКО свои предпочтения. Провижининг строки и token-unsubscribe идут под
-- service_role (обходит RLS). insert/delete из-под authenticated не даём — строку создаёт бэкенд.
drop policy if exists email_preferences_select on email_preferences;
create policy email_preferences_select on email_preferences
  for select using (user_id = auth.uid());
drop policy if exists email_preferences_update on email_preferences;
create policy email_preferences_update on email_preferences
  for update using (user_id = auth.uid()) with check (user_id = auth.uid());
revoke insert, delete on email_preferences from authenticated;
-- TRUNCATE обходит RLS (сносит предпочтения всех тенантов). Supabase дефолтно грантит его
-- authenticated на новой таблице — снимаем явно, как в 0002 для content-таблиц (M1 #8).
revoke truncate on email_preferences from authenticated;

-- ─────────────────────────────────────────── email_suppression: bounce/complaint, pre-send фильтр
-- Глобально-уникальный адрес (жалоба = не мейлить нигде), tenant_id для аудита. email хранится
-- в нижнем регистре (нормализация на стороне приложения). Control-таблица: только service_role.
create table if not exists email_suppression (
  id              bigint generated always as identity primary key,
  tenant_id       uuid references tenants(id) on delete set null,
  email           text not null unique,
  reason          text not null check (reason in ('bounce', 'complaint', 'manual')),
  source_event_id text,
  created_at      timestamptz not null default now()
);
alter table email_suppression enable row level security;
revoke all on email_suppression from authenticated;

-- ─────────────────────────────────────────── email_dispatch_log: идемпотентность + аудит отправок
-- dedup_key: для digest = run_id, для budget-threshold = 'YYYY-MM:pct', для welcome = user_id и т.п.
-- Уникальный индекс не даёт послать одно и то же дважды (insert-before-send). Control-таблица.
create table if not exists email_dispatch_log (
  id                bigint generated always as identity primary key,
  tenant_id         uuid references tenants(id) on delete set null,
  user_id           uuid references users(id) on delete set null,
  notification_type text not null,
  dedup_key         text not null,
  resend_email_id   text,
  status            text not null default 'sent',
  created_at        timestamptz not null default now(),
  unique (user_id, notification_type, dedup_key)
);
alter table email_dispatch_log enable row level security;
revoke all on email_dispatch_log from authenticated;
