import { describe, expect, it } from "vitest";
import { fieldKind } from "./adapters";

describe("fieldKind", () => {
  it("maps boolean", () => {
    expect(fieldKind({ type: "boolean" })).toBe("boolean");
  });

  it("maps integer/number", () => {
    expect(fieldKind({ type: "integer" })).toBe("number");
    expect(fieldKind({ type: "number" })).toBe("number");
  });

  it("maps enum to select", () => {
    expect(fieldKind({ type: "string", enum: ["a", "b"] })).toBe("select");
  });

  it("treats anyOf [string, null] as string", () => {
    expect(fieldKind({ anyOf: [{ type: "string" }, { type: "null" }] })).toBe("string");
  });

  it("defaults to string", () => {
    expect(fieldKind({})).toBe("string");
  });
});
