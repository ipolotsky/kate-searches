// Эскалация расхода к бюджету: ok < notice(50%) < upsell(threshold) < blocked(100%).
// notice — раннее уведомление, upsell — призыв к апгрейду, blocked — hard-cap (бэкенд не даёт
// генерить). Пороги считаются от usable-бюджета тенанта.

import { USAGE_NOTICE_PCT } from "./plans";

export type UsageLevel = "ok" | "notice" | "upsell" | "blocked";

// Math.floor, а не round: «100%» должно означать именно исчерпание (>=budget), а не 99.6%,
// округлённые вверх, — иначе баннер показывает 100% при ещё разрешённой генерации.
// budget<=0 трактуем как исчерпанный (бэкенд budget_exceeded блокирует при spent>=0).
export const usagePercent = (spent: number, budget: number): number =>
  budget > 0 ? Math.min(100, Math.floor((spent / budget) * 100)) : 100;

export const usageLevel = (spent: number, budget: number, thresholdPct: number): UsageLevel => {
  if (budget <= 0) {
    return "blocked";
  }
  const ratio = (spent / budget) * 100;
  if (ratio >= 100) {
    return "blocked";
  }
  if (ratio >= thresholdPct) {
    return "upsell";
  }
  if (ratio >= USAGE_NOTICE_PCT) {
    return "notice";
  }
  return "ok";
};

// Мелкие суммы (стоимость скоринга ~$0.0003) показываем с 4 знаками, крупные — с 2.
export const formatUsd = (value: number): string => {
  const decimals = value !== 0 && Math.abs(value) < 1 ? 4 : 2;
  return `$${value.toFixed(decimals)}`;
};

// Начало текущего календарного месяца в UTC (ISO) — граница окна расхода для запросов из web.
// Совпадает с бэкенд-хелпером month_start_utc() и RPC (date_trunc('month', now()) на UTC-сервере).
export const monthStartIso = (): string => {
  const now = new Date();
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1)).toISOString();
};
