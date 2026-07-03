-- KateSearches — начальная схема + RLS.
-- Мультитенант: каждая таблица с tenant_id, изоляция через RLS.
-- Применяется и локально (docker-entrypoint-initdb.d), и в Supabase (db push).

create extension if not exists "pgcrypto";

-- ─────────────────────────────────────────── Тенанты и пользователи

create table if not exists tenants (
  id                  uuid primary key default gen_random_uuid(),
  name                text not null,
  plan                text not null default 'pilot',         -- pilot | starter | pro | agency
  ai_budget_usd_month numeric not null default 15,
  ai_spent_usd_month  numeric not null default 0,
  upsell_threshold_pct int not null default 80,
  default_locale      text not null default 'en',            -- i18n: язык по умолчанию тенанта
  timezone            text not null default 'UTC',
  created_at          timestamptz not null default now()
);

-- users.id = supabase auth.users.id
create table if not exists users (
  id         uuid primary key,
  tenant_id  uuid not null references tenants(id) on delete cascade,
  email      text not null,
  role       text not null default 'editor' check (role in ('owner','editor','admin')),
  locale     text not null default 'en',
  created_at timestamptz not null default now()
);
create index if not exists idx_users_tenant on users(tenant_id);

-- ─────────────────────────────────────────── Профиль бренда

create table if not exists brand_profiles (
  id                  uuid primary key default gen_random_uuid(),
  tenant_id           uuid not null references tenants(id) on delete cascade,
  company_description text,
  audience_description text,
  filter_criteria     text,                  -- свободный текст «что берём / что отбрасываем»
  voice_config        jsonb not null default '{}'::jsonb,   -- тон, обороты
  voice_examples      jsonb not null default '[]'::jsonb,   -- [{post_text, source_url, why}] few-shot
  criteria_weights    jsonb not null default '{}'::jsonb,   -- веса критериев скоринга
  score_threshold     int not null default 60,              -- порог passes_threshold
  locales             text[] not null default '{en}',       -- языки контента тенанта
  files               jsonb not null default '[]'::jsonb,    -- загруженные брендбуки/примеры
  updated_at          timestamptz not null default now(),
  unique (tenant_id)
);

-- ─────────────────────────────────────────── Товары (CSV-загрузка)

create table if not exists products (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  external_id text,
  name        text not null,
  brand       text,
  category    text,
  url         text,
  price       numeric,
  attributes  jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);
create index if not exists idx_products_tenant on products(tenant_id);
create index if not exists idx_products_brand on products(tenant_id, brand);

-- ─────────────────────────────────────────── Источники

create table if not exists sources (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  type        text not null check (type in ('rss','scraper','sitemap','telegram','reddit')),
  url         text not null,
  title       text,
  priority    int not null default 3,        -- 1..5 уровень доверия (как в доках Kate)
  category    text,                          -- категория источника
  config      jsonb not null default '{}'::jsonb,
  state       jsonb not null default '{}'::jsonb,    -- курсор инкрементальности (ETag/last_pub/since_id)
  enabled     boolean not null default true,
  last_run_at timestamptz,
  created_at  timestamptz not null default now()
);
create index if not exists idx_sources_tenant on sources(tenant_id);

-- ─────────────────────────────────────────── Статьи (сырьё + извлечённое)

create table if not exists articles (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references tenants(id) on delete cascade,
  source_id       uuid references sources(id) on delete set null,
  url             text not null,
  canonical_url   text not null,
  external_id     text,
  title           text,
  body            text,
  summary         text,
  language        text,
  author          text,
  tags            text[] not null default '{}',
  media           jsonb not null default '[]'::jsonb,
  published_at    timestamptz,
  fetched_at      timestamptz not null default now(),
  content_hash    text,
  simhash         bigint,
  status          text not null default 'new'
                    check (status in ('new','extracted','filtered_out','scored','drafted')),
  relevance       jsonb,                     -- полный объект RelevanceScore
  relevance_score int,                       -- денормализованный для сортировки
  created_at      timestamptz not null default now(),
  unique (tenant_id, canonical_url)
);
create index if not exists idx_articles_tenant_status on articles(tenant_id, status);
create index if not exists idx_articles_published on articles(tenant_id, published_at desc);

-- ─────────────────────────────────────────── Посты (черновики)

create table if not exists posts (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references tenants(id) on delete cascade,
  article_id      uuid references articles(id) on delete set null,
  title           text,
  body_markdown   text,
  faq             jsonb not null default '[]'::jsonb,
  json_ld         jsonb,                     -- AEO: schema.org
  seo             jsonb not null default '{}'::jsonb,    -- meta, headings-инструкции
  suggested_titles text[] not null default '{}',
  linked_products jsonb not null default '[]'::jsonb,
  language        text,
  ai_model        text,
  ai_cost_usd     numeric,
  status          text not null default 'new'
                    check (status in ('new','in_progress','published','rejected','archived')),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
create index if not exists idx_posts_tenant_status on posts(tenant_id, status, created_at desc);

-- ─────────────────────────────────────────── Обратная связь

create table if not exists feedback (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  target_type text not null check (target_type in ('score','draft')),
  target_id   uuid not null,
  rating      int,                           -- -1 / +1 или 1..5
  edited_diff jsonb,                          -- дельта draft -> final (высший сигнал)
  comment     text,
  user_id     uuid references users(id) on delete set null,
  created_at  timestamptz not null default now()
);
create index if not exists idx_feedback_tenant on feedback(tenant_id, target_type);

-- ─────────────────────────────────────────── Учёт стоимости AI

create table if not exists ai_usage (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references tenants(id) on delete cascade,
  user_id       uuid references users(id) on delete set null,
  stage         text not null check (stage in ('score','draft','extract','other')),
  model         text,
  input_tokens  int,
  output_tokens int,
  cost_usd      numeric not null default 0,
  request_id    text,
  created_at    timestamptz not null default now()
);
create index if not exists idx_ai_usage_tenant_time on ai_usage(tenant_id, created_at);

-- ─────────────────────────────────────────── RLS

-- Helper: tenant_id текущего пользователя из его записи в users.
-- security definer: тело читает users в обход RLS. Без этого политика users_isolation
-- вызывает current_tenant_id(), который снова читает users под RLS → бесконечная рекурсия
-- политики (infinite recursion detected in policy for relation "users").
create or replace function current_tenant_id() returns uuid
language sql
stable
security definer
set search_path = public, auth
as $$
  select tenant_id from users where id = auth.uid()
$$;

do $$
declare t text;
begin
  foreach t in array array[
    'tenants','users','brand_profiles','products','sources',
    'articles','posts','feedback','ai_usage'
  ] loop
    execute format('alter table %I enable row level security;', t);
  end loop;
end $$;

-- Control-таблицы (tenants, users, ai_usage): authenticated только ЧИТАЕТ свой скоуп.
-- Запись — под service_role (провижининг, пайплайн, метеринг). Без SELECT-only участник
-- тенанта мог бы сам крутить бюджет/лимиты, эскалировать role до owner или снести тенант.
drop policy if exists tenants_isolation on tenants;
drop policy if exists tenants_select on tenants;
create policy tenants_select on tenants
  for select using (id = current_tenant_id());

drop policy if exists users_isolation on users;
drop policy if exists users_select on users;
create policy users_select on users
  for select using (tenant_id = current_tenant_id());

drop policy if exists ai_usage_isolation on ai_usage;
drop policy if exists ai_usage_select on ai_usage;
create policy ai_usage_select on ai_usage
  for select using (tenant_id = current_tenant_id());

-- Контент тенанта: полный CRUD в рамках своего tenant_id.
do $$
declare t text;
begin
  foreach t in array array[
    'brand_profiles','products','sources','articles','posts','feedback'
  ] loop
    execute format('drop policy if exists %1$s_isolation on %1$I;', t);
    execute format(
      'create policy %1$s_isolation on %1$I using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());',
      t
    );
  end loop;
end $$;

-- ─────────────────────────────────────────── Гранты для supabase-ролей
-- RLS включён, но сам по себе доступ к ТАБЛИЦЕ как объекту нужно выдать грантами,
-- иначе роль authenticated получает "permission denied for table" ещё до RLS.
-- Доступ к СТРОКАМ всё равно ограничен политиками выше.

grant usage on schema public to anon, authenticated, service_role;

grant select, insert, update, delete on all tables in schema public
  to authenticated, service_role;

-- Control-таблицы read-only для authenticated: write рубится и на уровне грантов
-- (RLS без permissive-политики на запись уже блокирует, это defense-in-depth).
revoke insert, update, delete on tenants, users, ai_usage from authenticated;

-- Будущие таблицы (миграции M1+) автоматически получат те же гранты.
alter default privileges in schema public
  grant select, insert, update, delete on tables to authenticated, service_role;

-- ПРИМЕЧАНИЕ: бэкенд-пайплайн и админка ходят под service_role (обходит RLS).
-- Пользовательские запросы из web идут под anon/authenticated и скоупятся RLS автоматически.
