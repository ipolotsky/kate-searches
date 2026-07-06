import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SourceTestResponse } from "@/lib/sources/adapters";
import { renderWithProviders } from "@/test/render";
import { SourceTestResult } from "./SourceTestResult";

describe("SourceTestResult", () => {
  it("shows a mapped error code label", () => {
    const response: SourceTestResponse = { ok: false, error: "fetch_timeout" };
    renderWithProviders(<SourceTestResult response={response} />);
    expect(screen.getByText("Fetch timed out")).toBeInTheDocument();
  });

  it("renders sample items with novelty and body flags", () => {
    const response: SourceTestResponse = {
      ok: true,
      sample: [
        {
          title: "Item one",
          url: "https://item.test",
          is_novel: true,
          language: "en",
          has_body: true,
          body_preview: "preview text",
          published_at: null,
        },
      ],
    };
    renderWithProviders(<SourceTestResult response={response} />);
    expect(screen.getByText("Item one")).toBeInTheDocument();
    expect(screen.getByText("New")).toBeInTheDocument();
    expect(screen.getByText("Has text")).toBeInTheDocument();
  });

  it("shows the empty-sample message", () => {
    renderWithProviders(<SourceTestResult response={{ ok: true, sample: [] }} />);
    expect(screen.getByText("No items returned.")).toBeInTheDocument();
  });
});
