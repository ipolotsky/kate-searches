import rehypeSanitize from "rehype-sanitize";
import rehypeStringify from "rehype-stringify";
import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import remarkRehype from "remark-rehype";
import { unified } from "unified";
import type { ExportablePost } from "./post";

const escapeHtml = (value: string): string =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

// md -> HTML через unified с rehype-sanitize: тело поста может нести AI-контент,
// поэтому санитайзим против XSS перед вставкой в документ.
const markdownToHtml = (markdown: string): string =>
  String(
    unified()
      .use(remarkParse)
      .use(remarkGfm)
      .use(remarkRehype)
      .use(rehypeSanitize)
      .use(rehypeStringify)
      .processSync(markdown),
  );

export const toHtml = (post: ExportablePost): string => {
  const parts: string[] = [];
  if (post.title.length > 0) {
    parts.push(`# ${post.title}`);
  }
  if (post.bodyMarkdown.trim().length > 0) {
    parts.push(post.bodyMarkdown.trim());
  }
  if (post.faq.length > 0) {
    const faqLines = post.faq.map((x) => `### ${x.question}\n\n${x.answer}`);
    parts.push(`## FAQ\n\n${faqLines.join("\n\n")}`);
  }

  const body = markdownToHtml(parts.join("\n\n"));

  // json_ld не проходит md-санитайзер (это отдельный script), поэтому сериализуем безопасно:
  // экранируем '<', чтобы значение строки не могло закрыть <script>.
  const jsonLdScript =
    post.jsonLd != null
      ? `\n  <script type="application/ld+json">\n${JSON.stringify(post.jsonLd, null, 2).replace(/</g, "\\u003c")}\n  </script>`
      : "";

  const metaDescription =
    post.seo.meta_description != null && post.seo.meta_description.length > 0
      ? `\n  <meta name="description" content="${escapeHtml(post.seo.meta_description)}" />`
      : "";

  return `<!doctype html>
<html lang="${escapeHtml(post.language ?? "en")}">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(post.title)}</title>${metaDescription}${jsonLdScript}
</head>
<body>
${body}</body>
</html>
`;
};
