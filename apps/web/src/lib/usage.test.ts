import { describe, expect, it } from "vitest";
import { DEFAULT_UPSELL_THRESHOLD_PCT, PLAN_CATALOG, RESERVED_MARGIN_PCT, isPlan } from "./plans";
import { formatUsd, usageLevel, usagePercent } from "./usage";

describe("usagePercent", () => {
  it("computes rounded percent of budget", () => {
    expect(usagePercent(5, 10)).toBe(50);
    expect(usagePercent(2.5, 10)).toBe(25);
  });

  it("caps at 100 when over budget", () => {
    expect(usagePercent(15, 10)).toBe(100);
  });

  it("floors so 100% means truly exhausted, not rounded up from 99.x%", () => {
    expect(usagePercent(9.96, 10)).toBe(99);
    expect(usagePercent(7.96, 10)).toBe(79);
  });

  it("returns 100 for non-positive budget (exhausted)", () => {
    expect(usagePercent(5, 0)).toBe(100);
  });
});

describe("usageLevel", () => {
  const threshold = DEFAULT_UPSELL_THRESHOLD_PCT;

  it("is ok below the notice threshold", () => {
    expect(usageLevel(4, 10, threshold)).toBe("ok");
  });

  it("is notice from 50% up to the upsell threshold", () => {
    expect(usageLevel(5, 10, threshold)).toBe("notice");
    expect(usageLevel(7.9, 10, threshold)).toBe("notice");
  });

  it("is upsell from the threshold up to 100%", () => {
    expect(usageLevel(8, 10, threshold)).toBe("upsell");
    expect(usageLevel(9.9, 10, threshold)).toBe("upsell");
  });

  it("is blocked at or above 100%", () => {
    expect(usageLevel(10, 10, threshold)).toBe("blocked");
    expect(usageLevel(12, 10, threshold)).toBe("blocked");
  });

  it("is blocked for non-positive budget (matches backend hard-cap at spent>=budget)", () => {
    expect(usageLevel(5, 0, threshold)).toBe("blocked");
    expect(usageLevel(0, 0, threshold)).toBe("blocked");
  });
});

describe("plan catalog", () => {
  it("derives usable budget as price minus reserved margin", () => {
    expect(PLAN_CATALOG.starter.usableBudget).toBeCloseTo(49 * (1 - RESERVED_MARGIN_PCT / 100), 2);
    expect(PLAN_CATALOG.pro.usableBudget).toBeCloseTo(129 * (1 - RESERVED_MARGIN_PCT / 100), 2);
  });

  it("gives pilot a fixed free-tier budget", () => {
    expect(PLAN_CATALOG.pilot.usableBudget).toBe(15);
    expect(PLAN_CATALOG.pilot.sources).toBeNull();
  });

  it("recognises known plans only", () => {
    expect(isPlan("pro")).toBe(true);
    expect(isPlan("enterprise")).toBe(false);
  });
});

describe("formatUsd", () => {
  it("shows four decimals for sub-dollar amounts", () => {
    expect(formatUsd(0.0003)).toBe("$0.0003");
  });

  it("shows two decimals for amounts at or above a dollar", () => {
    expect(formatUsd(12.5)).toBe("$12.50");
  });

  it("shows two decimals for zero", () => {
    expect(formatUsd(0)).toBe("$0.00");
  });
});
