import type { ExportablePost } from "./post";
import { toMarkdown } from "./toMarkdown";

export const copyAsText = async (post: ExportablePost): Promise<void> => {
  await navigator.clipboard.writeText(toMarkdown(post));
};
