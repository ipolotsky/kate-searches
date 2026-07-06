import { describe, expect, it } from "vitest";
import { buildEditedDiff, hasChanges } from "./diff";

describe("buildEditedDiff", () => {
  it("captures a unified patch with lengths", () => {
    const original = "Hello world";
    const edited = "Hello brave world";
    const diff = buildEditedDiff(original, edited);
    expect(diff.engine).toBe("jsdiff");
    expect(diff.format).toBe("unified");
    expect(diff.original_len).toBe(original.length);
    expect(diff.edited_len).toBe(edited.length);
    expect(diff.patch).toContain("brave");
  });

  it("produces a patch even with no textual change", () => {
    const diff = buildEditedDiff("same", "same");
    expect(diff.original_len).toBe(4);
    expect(diff.edited_len).toBe(4);
  });
});

describe("hasChanges", () => {
  it("detects changes", () => {
    expect(hasChanges("a", "b")).toBe(true);
    expect(hasChanges("a", "a")).toBe(false);
  });
});
