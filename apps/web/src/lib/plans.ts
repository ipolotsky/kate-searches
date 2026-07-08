// Каталог тарифов и бюджетная модель M5.
// usableBudget = месячный AI-бюджет (потолок фактического расхода). Дефолт выводится из цены
// тарифа за вычетом гарантированной маржи: price × (1 − RESERVED_MARGIN_PCT). Pilot бесплатный,
// поэтому у него фиксированный free-tier потолок. Админ может переопределить бюджет пер-тенант.
// Лимиты sources/drafts в M5 только справочные (энфорсим лишь денежный бюджет).

export const PLANS = ["pilot", "starter", "pro", "agency"] as const;

export type Plan = (typeof PLANS)[number];

export const RESERVED_MARGIN_PCT = 20;
export const DEFAULT_UPSELL_THRESHOLD_PCT = 80;
export const USAGE_NOTICE_PCT = 50;
export const PILOT_FREE_BUDGET_USD = 15;

// Триал (M6.2): value-fence лимиты по умолчанию. Совпадают с бэкендом (metering.py),
// per-tenant оверрайд — колонки tenants.trial_drafts_limit/trial_sources_limit.
export const TRIAL_DRAFTS_LIMIT = 10;
export const TRIAL_SOURCES_LIMIT = 3;

export interface PlanSpec {
  price: number;
  usableBudget: number;
  sources: number | null;
  drafts: number | null;
}

const usableBudgetOf = (price: number): number =>
  Math.round(price * (1 - RESERVED_MARGIN_PCT / 100) * 100) / 100;

export const PLAN_CATALOG: Record<Plan, PlanSpec> = {
  pilot: { price: 0, usableBudget: PILOT_FREE_BUDGET_USD, sources: null, drafts: null },
  starter: { price: 49, usableBudget: usableBudgetOf(49), sources: 5, drafts: 60 },
  pro: { price: 129, usableBudget: usableBudgetOf(129), sources: 20, drafts: 250 },
  agency: { price: 349, usableBudget: usableBudgetOf(349), sources: 60, drafts: 800 },
};

export const isPlan = (value: string): value is Plan =>
  (PLANS as readonly string[]).includes(value);
