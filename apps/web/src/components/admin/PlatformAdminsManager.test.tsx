import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { grantPlatformAdmin, revokePlatformAdmin } from "@/app/[locale]/(app)/_actions/admin";
import { renderWithProviders } from "@/test/render";
import { type AdminRow, PlatformAdminsManager } from "./PlatformAdminsManager";

vi.mock("@/app/[locale]/(app)/_actions/admin", () => ({
  grantPlatformAdmin: vi.fn(),
  revokePlatformAdmin: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const mockedGrant = vi.mocked(grantPlatformAdmin);
const mockedRevoke = vi.mocked(revokePlatformAdmin);

const rows: AdminRow[] = [
  { userId: "me", email: "me@x.test", createdAt: "2026-07-07T00:00:00Z" },
  { userId: "other", email: "other@x.test", createdAt: "2026-07-07T00:00:00Z" },
];

describe("PlatformAdminsManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("grants admin by typed email", async () => {
    mockedGrant.mockResolvedValue({ ok: true });
    renderWithProviders(<PlatformAdminsManager rows={rows} currentUserId="me" locale="en" />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@x.test" } });
    fireEvent.click(screen.getByText("Grant admin"));

    await waitFor(() => expect(mockedGrant).toHaveBeenCalledWith("new@x.test", "en"));
  });

  it("marks the current admin as 'you' and offers Remove for others", () => {
    renderWithProviders(<PlatformAdminsManager rows={rows} currentUserId="me" locale="en" />);
    expect(screen.getByText("you (current)")).toBeInTheDocument();
    expect(screen.getByText("Remove")).toBeInTheDocument();
  });

  it("revokes another admin by user id", async () => {
    mockedRevoke.mockResolvedValue({ ok: true });
    renderWithProviders(<PlatformAdminsManager rows={rows} currentUserId="me" locale="en" />);

    fireEvent.click(screen.getByText("Remove"));

    await waitFor(() => expect(mockedRevoke).toHaveBeenCalledWith("other", "en"));
  });

  it("shows an empty state with no admins", () => {
    renderWithProviders(<PlatformAdminsManager rows={[]} currentUserId="me" locale="en" />);
    expect(screen.getByText("No platform admins yet.")).toBeInTheDocument();
  });
});
