"use client";

import { Button, Card } from "flowbite-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { ExternalLinkIcon } from "@/components/ui/icons";
import { PriorityBadge } from "@/components/ui/PriorityBadge";
import { ScoreBadge } from "@/components/ui/ScoreBadge";
import { StatusActionButtons } from "@/components/ui/StatusActionButtons";
import type { PostStatus, PostView } from "@/lib/types";

interface PostCardProps {
  post: PostView;
  locale: string;
  pending: boolean;
  onAction: (next: PostStatus) => void;
}

export const PostCard: React.FC<PostCardProps> = (props) => {
  const t = useTranslations("post");
  const post = props.post;

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-2">
        {post.priority != null ? <PriorityBadge priority={post.priority} /> : null}
        {post.score != null ? <ScoreBadge score={post.score} label={t("score")} /> : null}
        {post.model != null ? (
          <span className="text-xs text-gray-400">{post.model}</span>
        ) : null}
      </div>

      <h3 className="text-base font-semibold leading-snug text-gray-900 dark:text-white">
        {post.title.length > 0 ? post.title : t("untitled")}
      </h3>

      {post.source != null ? (
        <a
          href={post.source.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          {t("source")}: {post.source.title ?? post.source.url}
          <ExternalLinkIcon className="h-3.5 w-3.5" />
        </a>
      ) : null}

      <div className="mt-1 flex flex-wrap items-center gap-2">
        <Button as={Link} href={`/${props.locale}/posts/${post.id}`} size="xs" color="blue">
          {t("actions.edit")}
        </Button>
        <StatusActionButtons status={post.status} pending={props.pending} onChange={props.onAction} />
      </div>
    </Card>
  );
};
