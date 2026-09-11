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

const freshCandidate1: CandidateView = {
  id: "fresh-1",
  title: "Fresh story 1",
  url: "https://fresh1.test",
  score: 85,
  priority: "HOT",
  source: { title: "TechNews", url: "https://technews.test" },
  createdAt: new Date().toISOString(),
  isNew: true,
};

const freshCandidate2: CandidateView = {
  id: "fresh-2",
  title: "Fresh story 2",
  url: "https://fresh2.test",
  score: 75,
  priority: "WARM",
  source: null,
  createdAt: new Date().toISOString(),
  isNew: true,
};

const oldCandidate1: CandidateView = {
  id: "old-1",
  title: "Previous story 1",
  url: "https://old1.test",
  score: 65,
  priority: "WARM",
  source: { title: "FashionBlog", url: "https://fashion.test" },
  createdAt: new Date(Date.now() - 48 * 3600 * 1000).toISOString(),
  isNew: false,
};

const oldCandidate2: CandidateView = {
  id: "old-2",
  title: "Previous story 2",
  url: "https://old2.test",
  score: 55,
  priority: "COLD",
  source: null,
  createdAt: new Date(Date.now() - 72 * 3600 * 1000).toISOString(),
  isNew: false,
};

describe("ScoredCandidates", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when candidate list is empty", () => {
    const { container } = renderWithProviders(<ScoredCandidates candidates={[]} locale="en" />);
    expect(container.querySelector("section")).toBeNull();
  });

  it("renders recent and previous sections when both exist, with previous collapsed initially", () => {
    renderWithProviders(
      <ScoredCandidates
        candidates={[freshCandidate1, freshCandidate2, oldCandidate1, oldCandidate2]}
        locale="en"
      />,
    );

    expect(screen.getByText("Recent stories")).toBeInTheDocument();
    expect(screen.getByText("Fresh story 1")).toBeInTheDocument();
    expect(screen.getByText("Fresh story 2")).toBeInTheDocument();

    expect(screen.getByText("Previous stories")).toBeInTheDocument();
    expect(screen.queryByText("Previous story 1")).not.toBeInTheDocument();
    expect(screen.queryByText("Previous story 2")).not.toBeInTheDocument();
  });

  it("expands previous stories when accordion is clicked and collapses on next click", () => {
    renderWithProviders(
      <ScoredCandidates
        candidates={[freshCandidate1, oldCandidate1, oldCandidate2]}
        locale="en"
      />,
    );

    expect(screen.queryByText("Previous story 1")).not.toBeInTheDocument();

    const accordionBtn = screen.getByRole("button", { name: /Previous stories/i });
    fireEvent.click(accordionBtn);

    expect(screen.getByText("Previous story 1")).toBeInTheDocument();
    expect(screen.getByText("Previous story 2")).toBeInTheDocument();

    fireEvent.click(accordionBtn);
    expect(screen.queryByText("Previous story 1")).not.toBeInTheDocument();
  });

  it("toggles all recent candidates with select all recent checkbox", () => {
    renderWithProviders(
      <ScoredCandidates
        candidates={[freshCandidate1, freshCandidate2, oldCandidate1]}
        locale="en"
      />,
    );

    const selectAllRecent = screen.getByLabelText("Select all recent");
    fireEvent.click(selectAllRecent);

    expect(screen.getByLabelText("Fresh story 1")).toBeChecked();
    expect(screen.getByLabelText("Fresh story 2")).toBeChecked();
    expect(screen.getByText("Generate drafts (2)")).toBeInTheDocument();

    fireEvent.click(selectAllRecent);
    expect(screen.getByLabelText("Fresh story 1")).not.toBeChecked();
    expect(screen.getByLabelText("Fresh story 2")).not.toBeChecked();
  });

  it("toggles all previous candidates independently", () => {
    renderWithProviders(
      <ScoredCandidates
        candidates={[freshCandidate1, oldCandidate1, oldCandidate2]}
        locale="en"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Previous stories/i }));

    const selectAllPrevious = screen.getByLabelText("Select all previous");
    fireEvent.click(selectAllPrevious);

    expect(screen.getByLabelText("Previous story 1")).toBeChecked();
    expect(screen.getByLabelText("Previous story 2")).toBeChecked();
    expect(screen.getByLabelText("Fresh story 1")).not.toBeChecked();
    expect(screen.getByText("Generate drafts (2)")).toBeInTheDocument();

    fireEvent.click(selectAllPrevious);
    expect(screen.getByLabelText("Previous story 1")).not.toBeChecked();
    expect(screen.getByLabelText("Previous story 2")).not.toBeChecked();
  });

  it("sends selected ids from both recent and previous when generating drafts", async () => {
    mockedGenerate.mockResolvedValue({ ok: true });
    renderWithProviders(
      <ScoredCandidates
        candidates={[freshCandidate1, oldCandidate1]}
        locale="en"
      />,
    );

    fireEvent.click(screen.getByLabelText("Fresh story 1"));

    fireEvent.click(screen.getByRole("button", { name: /Previous stories/i }));
    fireEvent.click(screen.getByLabelText("Previous story 1"));

    const generateBtn = screen.getByRole("button", { name: /Generate drafts \(2\)/i });
    fireEvent.click(generateBtn);

    await waitFor(() => {
      expect(mockedGenerate).toHaveBeenCalledWith(["fresh-1", "old-1"], "en");
    });
  });

  it("keeps generate button disabled when no items are selected", () => {
    renderWithProviders(
      <ScoredCandidates
        candidates={[freshCandidate1, oldCandidate1]}
        locale="en"
      />,
    );

    const generateBtn = screen.getByRole("button", { name: /Generate drafts \(0\)/i });
    expect(generateBtn).toBeDisabled();
  });

  it("renders a single list without accordion when only recent candidates exist", () => {
    renderWithProviders(
      <ScoredCandidates candidates={[freshCandidate1, freshCandidate2]} locale="en" />,
    );

    expect(screen.queryByText("Previous stories")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Select all")).toBeInTheDocument();
    expect(screen.getByText("Fresh story 1")).toBeInTheDocument();
    expect(screen.getByText("Fresh story 2")).toBeInTheDocument();
  });

  it("renders a single list without accordion when only previous candidates exist", () => {
    renderWithProviders(
      <ScoredCandidates candidates={[oldCandidate1, oldCandidate2]} locale="en" />,
    );

    expect(screen.queryByText("Recent stories")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Select all")).toBeInTheDocument();
    expect(screen.getByText("Previous story 1")).toBeInTheDocument();
    expect(screen.getByText("Previous story 2")).toBeInTheDocument();
  });
});
