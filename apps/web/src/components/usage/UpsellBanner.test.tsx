import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/render";
import { UpsellBanner } from "./UpsellBanner";

const { mockUsePathname } = vi.hoisted(() => ({
  mockUsePathname: vi.fn(() => "/en/dashboard"),
}));

vi.mock("next/navigation", () => ({ usePathname: mockUsePathname }));

describe("UpsellBanner", () => {
  afterEach(() => {
    mockUsePathname.mockReturnValue("/en/dashboard");
  });

  it("renders nothing at level ok", () => {
    renderWithProviders(<UpsellBanner level="ok" percent={10} locale="en" />);
    expect(screen.queryByText(/budget/i)).not.toBeInTheDocument();
  });

  it("shows the blocked message with a usage CTA", () => {
    renderWithProviders(<UpsellBanner level="blocked" percent={100} locale="en" />);
    expect(screen.getByText("Monthly budget reached")).toBeInTheDocument();
    const cta = screen.getByRole("link", { name: "View usage" });
    expect(cta).toHaveAttribute("href", "/en/usage");
  });

  it("interpolates percent into the upsell title", () => {
    renderWithProviders(<UpsellBanner level="upsell" percent={85} locale="en" />);
    expect(screen.getByText(/85% of your monthly budget/)).toBeInTheDocument();
  });

  it("hides the CTA when showCta is false", () => {
    renderWithProviders(<UpsellBanner level="notice" percent={55} locale="en" showCta={false} />);
    expect(screen.queryByRole("link", { name: "View usage" })).not.toBeInTheDocument();
  });

  it("suppresses itself on the /usage route when asked", () => {
    mockUsePathname.mockReturnValue("/en/usage");
    renderWithProviders(
      <UpsellBanner level="blocked" percent={100} locale="en" suppressOnUsage />,
    );
    expect(screen.queryByText("Monthly budget reached")).not.toBeInTheDocument();
  });

  it("still renders on non-usage routes when suppressOnUsage is set", () => {
    mockUsePathname.mockReturnValue("/en/dashboard");
    renderWithProviders(
      <UpsellBanner level="blocked" percent={100} locale="en" suppressOnUsage />,
    );
    expect(screen.getByText("Monthly budget reached")).toBeInTheDocument();
  });
});
