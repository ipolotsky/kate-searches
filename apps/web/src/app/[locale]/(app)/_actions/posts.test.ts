import { beforeEach, describe, expect, it, vi } from "vitest";
import { createClient } from "@/lib/supabase/server";
import { updatePostStatus } from "./posts";

vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("@/lib/auth/tenant", () => ({
  getUserAndTenant: vi.fn().mockResolvedValue({ tenantId: "t1", userId: "u1" }),
}));
vi.mock("@/lib/supabase/server", () => ({ createClient: vi.fn() }));

interface QueryResult {
  data: unknown;
  error: unknown;
}

const makeSupabase = (read: QueryResult, cas: QueryResult) => {
  const eqCalls: [string, unknown][] = [];
  const readBuilder = {
    eq: vi.fn(() => readBuilder),
    maybeSingle: vi.fn(() => Promise.resolve(read)),
  };
  const updateBuilder = {
    eq: vi.fn((column: string, value: unknown) => {
      eqCalls.push([column, value]);
      return updateBuilder;
    }),
    select: vi.fn(() => Promise.resolve(cas)),
  };
  const table = {
    select: vi.fn(() => readBuilder),
    update: vi.fn(() => updateBuilder),
  };
  const client = { from: vi.fn(() => table) };
  return { client, table, eqCalls };
};

const useClient = (client: unknown): void => {
  vi.mocked(createClient).mockResolvedValue(
    client as unknown as Awaited<ReturnType<typeof createClient>>,
  );
};

describe("updatePostStatus (compare-and-swap)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("legal transition on unchanged status succeeds and gates the write on `from`", async () => {
    const supabase = makeSupabase(
      { data: { status: "new" }, error: null },
      { data: [{ id: "p1" }], error: null },
    );
    useClient(supabase.client);

    const result = await updatePostStatus("p1", "in_progress", "en");

    expect(result).toEqual({ ok: true });
    // CAS: UPDATE скоуплен и по id, и по исходному статусу.
    expect(supabase.eqCalls).toContainEqual(["id", "p1"]);
    expect(supabase.eqCalls).toContainEqual(["status", "new"]);
  });

  it("returns conflict when the row was moved concurrently (zero affected rows)", async () => {
    const supabase = makeSupabase(
      { data: { status: "in_progress" }, error: null },
      { data: [], error: null },
    );
    useClient(supabase.client);

    const result = await updatePostStatus("p1", "published", "en");

    expect(result).toEqual({ ok: false, code: "conflict" });
  });

  it("rejects an illegal transition before any write", async () => {
    const supabase = makeSupabase(
      { data: { status: "published" }, error: null },
      { data: [{ id: "p1" }], error: null },
    );
    useClient(supabase.client);

    const result = await updatePostStatus("p1", "new", "en");

    expect(result).toEqual({ ok: false, code: "illegalTransition" });
    expect(supabase.table.update).not.toHaveBeenCalled();
  });

  it("returns notFound when the post is not visible", async () => {
    const supabase = makeSupabase({ data: null, error: null }, { data: [], error: null });
    useClient(supabase.client);

    const result = await updatePostStatus("missing", "in_progress", "en");

    expect(result).toEqual({ ok: false, code: "notFound" });
  });

  it("returns updateFailed on a write error", async () => {
    const supabase = makeSupabase(
      { data: { status: "new" }, error: null },
      { data: null, error: { message: "boom" } },
    );
    useClient(supabase.client);

    const result = await updatePostStatus("p1", "in_progress", "en");

    expect(result).toEqual({ ok: false, code: "updateFailed" });
  });
});
