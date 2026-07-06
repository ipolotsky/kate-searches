import { describe, expect, it } from "vitest";
import type { ExportablePost } from "./post";
import { toMarkdown } from "./toMarkdown";

const base: ExportablePost = {
  title: "Resale is booming",
  bodyMarkdown: "## Intro\n\nThe market shifts.",
  faq: [{ question: "Is it real?", answer: "Yes, verified." }],
  jsonLd: null,
  seo: {},
  suggestedTitles: ["Alt title one", "Alt title two"],
  language: "en",
};

describe("toMarkdown", () => {
  it("renders title, body, FAQ and suggested titles", () => {
    const output = toMarkdown(base);
    expect(output).toContain("# Resale is booming");
    expect(output).toContain("## Intro");
    expect(output).toContain("## FAQ");
    expect(output).toContain("### Is it real?");
    expect(output).toContain("Yes, verified.");
    expect(output).toContain("- Alt title one");
  });

  it("omits empty sections", () => {
    const output = toMarkdown({ ...base, faq: [], suggestedTitles: [], title: "" });
    expect(output).not.toContain("## FAQ");
    expect(output).not.toContain("Suggested titles");
    expect(output.startsWith("# ")).toBe(false);
  });
});
