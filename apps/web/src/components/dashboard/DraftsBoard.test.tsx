import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { updatePostStatus } from "@/app/[locale]/(app)/_actions/posts";
import type { PostView } from "@/lib/types";
import { renderWithProviders } from "@/test/render";
import { DraftsBoard } from "./DraftsBoard";

vi.mock("@/app/[locale]/(app)/_actions/posts", () => ({
  updatePostStatus: vi.fn(),
}));

const mockedUpdate = vi.mocked(updatePostStatus);

const post: PostView = {
  id: "p1",
  title: "Draft one",
  status: "new",
  model: "gpt",
  updatedAt: "2026-01-01T00:00:00Z",
  priority: "HOT",
  score: 80,
  articleId: "a1",
  source: { title: "Src", url: "https://source.test" },
};

describe("DraftsBoard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("optimistically moves a post to in_progress on success", async () => {
    mockedUpdate.mockResolvedValue({ ok: true });
    renderWithProviders(<DraftsBoard posts={[post]} locale="en" />);

    fireEvent.click(screen.getByText("Take"));

    await waitFor(() => {
      expect(mockedUpdate).toHaveBeenCalledWith("p1", "in_progress", "en");
    });
    await waitFor(() => {
      expect(screen.getByText("In progress")).toBeInTheDocument();
    });
  });

  it("reverts to new on failure", async () => {
    mockedUpdate.mockResolvedValue({ ok: false, code: "updateFailed" });
    renderWithProviders(<DraftsBoard posts={[post]} locale="en" />);

    fireEvent.click(screen.getByText("Take"));

    await waitFor(() => {
      expect(mockedUpdate).toHaveBeenCalled();
    });
    // reverted: still in the New section, Take button available again
    await waitFor(() => {
      expect(screen.getByText("New")).toBeInTheDocument();
      expect(screen.getByText("Take")).toBeInTheDocument();
    });
  });
});
