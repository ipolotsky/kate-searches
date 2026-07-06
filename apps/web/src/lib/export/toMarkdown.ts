import type { ExportablePost } from "./post";

// Собирает пост в единый Markdown: заголовок -> тело -> FAQ -> предложенные заголовки.
export const toMarkdown = (post: ExportablePost): string => {
  const blocks: string[] = [];

  if (post.title.length > 0) {
    blocks.push(`# ${post.title}`);
  }

  if (post.bodyMarkdown.trim().length > 0) {
    blocks.push(post.bodyMarkdown.trim());
  }

  if (post.faq.length > 0) {
    const faqLines = post.faq.map((x) => `### ${x.question}\n\n${x.answer}`);
    blocks.push(`## FAQ\n\n${faqLines.join("\n\n")}`);
  }

  if (post.suggestedTitles.length > 0) {
    const titleLines = post.suggestedTitles.map((x) => `- ${x}`);
    blocks.push(`## Suggested titles\n\n${titleLines.join("\n")}`);
  }

  return `${blocks.join("\n\n")}\n`;
};
