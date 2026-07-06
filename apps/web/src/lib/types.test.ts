import { describe, expect, it } from "vitest";
import {
  extractCriteria,
  isCriterionScore,
  parseFaq,
  parseVoiceExamples,
  priorityOf,
} from "./types";

const relevance = {
  overall_score: 82,
  publication_priority: "HOT",
  passes_threshold: true,
  trend_explanation: "resale trend",
  decision_summary: "take it",
  news_potential: { reasoning: "fresh", score: "high" },
  seo_potential: { reasoning: "keyword rich", score: "medium" },
};

describe("extractCriteria", () => {
  it("returns only criterion-shaped fields, not scalars", () => {
    const criteria = extractCriteria(relevance);
    const keys = criteria.map((x) => x.key).sort();
    expect(keys).toEqual(["news_potential", "seo_potential"]);
    expect(criteria.find((x) => x.key === "news_potential")?.score).toBe("high");
  });

  it("handles non-object input", () => {
    expect(extractCriteria(null)).toEqual([]);
    expect(extractCriteria("nope")).toEqual([]);
  });
});

describe("isCriterionScore", () => {
  it("validates shape", () => {
    expect(isCriterionScore({ reasoning: "x", score: "low" })).toBe(true);
    expect(isCriterionScore({ reasoning: "x", score: "bogus" })).toBe(false);
    expect(isCriterionScore({ score: "low" })).toBe(false);
  });
});

describe("priorityOf", () => {
  it("reads publication_priority from relevance", () => {
    expect(priorityOf(relevance)).toBe("HOT");
    expect(priorityOf({ publication_priority: "NOPE" })).toBeNull();
    expect(priorityOf(null)).toBeNull();
  });
});

describe("parseFaq", () => {
  it("keeps only valid faq items", () => {
    const faq = parseFaq([
      { question: "q", answer: "a" },
      { question: "only-q" },
      "bad",
    ]);
    expect(faq).toEqual([{ question: "q", answer: "a" }]);
  });
});

describe("parseVoiceExamples", () => {
  it("normalizes missing fields to empty strings", () => {
    const examples = parseVoiceExamples([{ post_text: "hi" }]);
    expect(examples).toEqual([{ post_text: "hi", source_url: "", why: "" }]);
  });
});
