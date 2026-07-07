import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "@/test/render";
import { AdminTenantsTable, type TenantReportRow } from "./AdminTenantsTable";

const row: TenantReportRow = {
  tenant_id: "t-1",
  name: "Acme",
  plan: "pro",
  ai_budget_usd_month: 103.2,
  upsell_threshold_pct: 80,
  spend_month: 51.6,
  drafts_month: 12,
  users_count: 3,
  created_at: "2026-07-07T10:00:00Z",
};

describe("AdminTenantsTable", () => {
  it("renders a tenant row with formatted money, percent and a detail link", () => {
    renderWithProviders(<AdminTenantsTable rows={[row]} locale="en" />);

    const link = screen.getByRole("link", { name: "Acme" });
    expect(link).toHaveAttribute("href", "/en/admin/t-1");
    expect(screen.getByText("$51.60")).toBeInTheDocument();
    expect(screen.getByText("$103.20")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("2026-07-07")).toBeInTheDocument();
  });

  it("shows an empty state when there are no tenants", () => {
    renderWithProviders(<AdminTenantsTable rows={[]} locale="en" />);
    expect(screen.getByText("No tenants yet.")).toBeInTheDocument();
  });
});
