import type { PostStatus } from "@/lib/types";

// Машина состояний поста (docs/04 §5): new -> in_progress -> published; в любой момент
// reject/archive; возврат в new. Легальность перехода проверяется и в UI (какие кнопки
// показать), и в server action до UPDATE.
const TRANSITIONS: Record<PostStatus, PostStatus[]> = {
  new: ["in_progress", "rejected", "archived"],
  in_progress: ["published", "rejected", "archived", "new"],
  published: ["in_progress", "archived"],
  rejected: ["new", "archived"],
  archived: ["new"],
};

export const canTransition = (from: PostStatus, to: PostStatus): boolean =>
  TRANSITIONS[from]?.includes(to) ?? false;

export const availableTransitions = (from: PostStatus): PostStatus[] => TRANSITIONS[from] ?? [];
