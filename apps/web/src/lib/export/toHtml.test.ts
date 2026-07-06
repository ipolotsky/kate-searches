import { describe, expect, it } from "vitest";
import type { ExportablePost } from "./post";
import { toHtml } from "./toHtml";

const base: ExportablePost = {
  title: "Resale <b>booms</b>",
  bodyMarkdown: "## Intro\n\nText with a [link](https://example.com).",
  faq: [{ question: "Q?", answer: "A." }],
  jsonLd: { "@context": "https://schema.org", "@type": "Article" },
  seo: { meta_description: "Short desc" },
  suggestedTitles: [],
  language: "en",
};

describe("toHtml", () => {
  it("renders a full document with meta and json-ld", () => {
    const html = toHtml(base);
    expect(html).toContain("<!doctype html>");
    expect(html).toContain('<meta name="description" content="Short desc"');
    expect(html).toContain('type="application/ld+json"');
    expect(html).toContain('"@type": "Article"');
    expect(html).toContain("<h2");
    expect(html).toContain("FAQ");
  });

  it("escapes the title in <title>", () => {
    const html = toHtml(base);
    expect(html).toContain("<title>Resale &lt;b&gt;booms&lt;/b&gt;</title>");
  });

  it("uses the draft language for <html lang>, falling back to en", () => {
    expect(toHtml({ ...base, language: "ru" })).toContain('<html lang="ru">');
    expect(toHtml({ ...base, language: null })).toContain('<html lang="en">');
  });

  it("sanitizes dangerous markdown (no raw script survives)", () => {
    const html = toHtml({
      ...base,
      jsonLd: null,
      bodyMarkdown: "Hello <script>alert('xss')</script> world",
    });
    expect(html).not.toContain("<script>alert");
  });

  it("escapes '<' inside serialized json-ld", () => {
    const html = toHtml({ ...base, jsonLd: { name: "</script><script>evil" } });
    expect(html).not.toContain("</script><script>evil");
    expect(html).toContain("\\u003c");
  });
});
