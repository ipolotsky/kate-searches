-- KateSearches — веха M6.2 (биллинг + триал, Stripe test-mode). Аддитивно поверх 0007, идемпотентно.
-- Stripe = источник правды по плану/статусу подписки; наш ledger — энфорс COGS. Мост между ними —
-- одно число tenants.ai_budget_usd_month, которое проставляет вебхук по маппингу price->plan->budget.
-- Новых enforcement-механик нет: reserve/settle из 0006 переиспользуются (на триале период='trial').

-- ─────────────────────────────────────────── tenants: привязка Stripe + состояние подписки/триала
alter table tenants add column if not exists stripe_customer_id text;
alter table tenants add column if not exists stripe_subscription_id text;
-- trialing | active | past_due | canceled | unpaid | null (нет подписки)
alter table tenants add column if not exists subscription_status text;
alter table tenants add column if not exists current_period_end timestamptz;
-- Конец триала (зеркало Stripe subscription.trial_end): UI-метр + expiry-guard энфорса.
alter table tenants add column if not exists trial_ends_at timestamptz;
-- Allowlist: кто доходит до Stripe Checkout (в test-mode пускаем только приглашённых).
alter table tenants add column if not exists billing_enabled boolean not null default false;
-- Триал-лимиты per-tenant (null = глобальный дефолт из кода): value-fence, не денежная механика.
alter table tenants add column if not exists trial_drafts_limit int;
alter table tenants add column if not exists trial_sources_limit int;

-- ─────────────────────────────────────────── stripe_events: дедуп вебхуков (idempotency)
-- Один и тот же event Stripe может прийти больше одного раза — обрабатываем ровно раз по event_id.
-- Control-таблица: пишет только service_role (вебхук под admin-клиентом), authenticated не трогает.
create table if not exists stripe_events (
  event_id    text primary key,
  type        text,
  received_at timestamptz not null default now()
);
alter table stripe_events enable row level security;
revoke all on stripe_events from authenticated;
