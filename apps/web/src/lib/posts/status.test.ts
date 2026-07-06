import { describe, expect, it } from "vitest";
import { availableTransitions, canTransition } from "./status";

describe("post status machine", () => {
  it("allows new -> in_progress -> published", () => {
    expect(canTransition("new", "in_progress")).toBe(true);
    expect(canTransition("in_progress", "published")).toBe(true);
  });

  it("forbids new -> published (must go through in_progress)", () => {
    expect(canTransition("new", "published")).toBe(false);
  });

  it("allows reject and archive from active states", () => {
    expect(canTransition("new", "rejected")).toBe(true);
    expect(canTransition("in_progress", "archived")).toBe(true);
  });

  it("allows returning to new", () => {
    expect(canTransition("rejected", "new")).toBe(true);
    expect(canTransition("archived", "new")).toBe(true);
    expect(canTransition("in_progress", "new")).toBe(true);
  });

  it("forbids no-op transition", () => {
    expect(canTransition("new", "new")).toBe(false);
  });

  it("lists available transitions", () => {
    expect(availableTransitions("new")).toEqual(["in_progress", "rejected", "archived"]);
    expect(availableTransitions("archived")).toEqual(["new"]);
  });
});
