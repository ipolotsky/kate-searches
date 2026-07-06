import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { generateDrafts } from "@/app/[locale]/(app)/_actions/pipeline";
import type { CandidateView } from "@/lib/types";
import { renderWithProviders } from "@/test/render";
import { ScoredCandidates } from "./ScoredCandidates";

vi.mock("@/app/[locale]/(app)/_actions/pipeline", () => ({
  generateDrafts: vi.fn(),
}));

const mockedGenerate = vi.mocked(generateDrafts);

const candidate: CandidateView = {
  id: "a1",
  title: "Story one",
  url: "https://story.test",
  score: 70,
  priority: "WARM",
  source: null,
};

describe("ScoredCandidates", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sends the selected article ids to generateDrafts", async () => {
    mockedGenerate.mockResolvedValue({ ok: true });
    renderWithProviders(<ScoredCandidates candidates={[candidate]} locale="en" />);

    fireEvent.click(screen.getByLabelText("Story one"));
    fireEvent.click(screen.getByText(/Generate drafts/));

    await waitFor(() => {
      expect(mockedGenerate).toHaveBeenCalledWith(["a1"], "en");
    });
  });

  it("keeps generate disabled with no selection", () => {
    renderWithProviders(<ScoredCandidates candidates={[candidate]} locale="en" />);
    const button = screen.getByText(/Generate drafts/).closest("button");
    expect(button).toBeDisabled();
  });
});
