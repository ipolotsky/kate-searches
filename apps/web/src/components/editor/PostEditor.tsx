"use client";

import { Button, Label, Tabs, TabItem, TextInput } from "flowbite-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { type ActionResult, savePost, updatePostStatus } from "@/app/[locale]/(app)/_actions/posts";
import { RelevancePanel } from "@/components/article/RelevancePanel";
import { ScoreFeedback } from "@/components/article/ScoreFeedback";
import { SourceOriginal } from "@/components/article/SourceOriginal";
import { ArrowLeftIcon } from "@/components/ui/icons";
import { useToast } from "@/components/ui/ToastProvider";
import type { ExportablePost } from "@/lib/export/post";
import type {
  ArticleOriginal,
  FaqItem,
  PostSeo,
  PostStatus,
  RelevanceScore,
  SourceRef,
} from "@/lib/types";
import { DraftFeedback } from "./DraftFeedback";
import { ExportMenu } from "./ExportMenu";
import { FaqEditor } from "./FaqEditor";
import { JsonLdPreview } from "./JsonLdPreview";
import { MarkdownField } from "./MarkdownField";
import { SeoPanel } from "./SeoPanel";
import { StatusBar } from "./StatusBar";

export interface EditablePost {
  id: string;
  title: string;
  bodyMarkdown: string;
  faq: FaqItem[];
  jsonLd: Record<string, unknown> | null;
  seo: PostSeo;
  suggestedTitles: string[];
  language: string | null;
  status: PostStatus;
  model: string | null;
}

interface PostEditorProps {
  post: EditablePost;
  article: { original: ArticleOriginal; relevance: RelevanceScore | null } | null;
  source: SourceRef | null;
  locale: string;
}

type SaveState = "idle" | "saving" | "saved" | "error";

const AUTOSAVE_DELAY_MS = 1500;

export const PostEditor: React.FC<PostEditorProps> = (props) => {
  const t = useTranslations("editor");
  const toast = useToast();

  const [title, setTitle] = useState(props.post.title);
  const [body, setBody] = useState(props.post.bodyMarkdown);
  const [faq, setFaq] = useState<FaqItem[]>(props.post.faq);
  const [jsonLd, setJsonLd] = useState<Record<string, unknown> | null>(props.post.jsonLd);
  const [status, setStatus] = useState<PostStatus>(props.post.status);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [dirty, setDirty] = useState(false);
  const [statusPending, setStatusPending] = useState(false);

  const pristineBody = useRef(props.post.bodyMarkdown);
  const latest = useRef({ title, body, faq, jsonLd });
  latest.current = { title, body, faq, jsonLd };
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);

  useEffect(
    () => () => {
      mounted.current = false;
      if (timer.current != null) {
        clearTimeout(timer.current);
      }
    },
    [],
  );

  const flush = useCallback(async (): Promise<ActionResult> => {
    if (timer.current != null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    const snapshot = latest.current;
    setSaveState("saving");
    const result = await savePost(
      props.post.id,
      {
        title: snapshot.title,
        body_markdown: snapshot.body,
        faq: snapshot.faq,
        json_ld: snapshot.jsonLd,
      },
      props.locale,
    );
    if (!mounted.current) {
      return result;
    }
    if (result.ok) {
      setSaveState("saved");
      setDirty(false);
    } else {
      setSaveState("error");
      toast.show(t("saveError"), "error");
    }
    return result;
  }, [props.post.id, props.locale, t, toast]);

  const markDirty = useCallback((): void => {
    setDirty(true);
    if (timer.current != null) {
      clearTimeout(timer.current);
    }
    timer.current = setTimeout(() => {
      void flush();
    }, AUTOSAVE_DELAY_MS);
  }, [flush]);

  const changeStatus = useCallback(
    async (next: PostStatus): Promise<void> => {
      const saved = await flush();
      if (!saved.ok) {
        return;
      }
      setStatusPending(true);
      const result = await updatePostStatus(props.post.id, next, props.locale);
      setStatusPending(false);
      if (result.ok) {
        setStatus(next);
        toast.show(t("statusUpdated"), "success");
      } else {
        toast.show(t("statusFailed"), "error");
      }
    },
    [flush, props.post.id, props.locale, t, toast],
  );

  const indicator =
    saveState === "saving"
      ? t("saving")
      : saveState === "error"
        ? t("saveError")
        : dirty
          ? t("unsaved")
          : saveState === "saved"
            ? t("saved")
            : "";

  const exportable: ExportablePost = {
    title,
    bodyMarkdown: body,
    faq,
    jsonLd,
    seo: props.post.seo,
    suggestedTitles: props.post.suggestedTitles,
    language: props.post.language,
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button as={Link} href={`/${props.locale}/dashboard`} color="light" size="sm">
          <ArrowLeftIcon className="mr-2 h-4 w-4" />
          {t("back")}
        </Button>
        <div className="flex items-center gap-3">
          <span
            className={`text-xs ${saveState === "error" ? "text-red-500" : "text-gray-400"}`}
            aria-live="polite"
          >
            {indicator}
          </span>
          <ExportMenu post={exportable} fallbackName={props.post.id} />
        </div>
      </div>

      <StatusBar status={status} pending={statusPending} onChange={changeStatus} />

      <div>
        <Label htmlFor="post-title" className="mb-1 block">
          {t("titleLabel")}
        </Label>
        <TextInput
          id="post-title"
          value={title}
          onChange={(event) => {
            setTitle(event.target.value);
            markDirty();
          }}
          onBlur={() => void flush()}
        />
      </div>

      <Tabs aria-label={t("tabs.aria")} variant="underline">
        <TabItem active title={t("tabs.body")}>
          <div className="flex flex-col gap-6">
            <MarkdownField
              value={body}
              onChange={(value) => {
                setBody(value);
                markDirty();
              }}
              onBlur={() => void flush()}
            />
            <section>
              <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-white">
                {t("faq.title")}
              </h3>
              <FaqEditor
                value={faq}
                onChange={(value) => {
                  setFaq(value);
                  markDirty();
                }}
              />
            </section>
            <section>
              <JsonLdPreview
                value={jsonLd}
                onChange={(value) => {
                  setJsonLd(value);
                  markDirty();
                }}
              />
            </section>
          </div>
        </TabItem>

        <TabItem title={t("tabs.seo")}>
          <SeoPanel seo={props.post.seo} suggestedTitles={props.post.suggestedTitles} />
        </TabItem>

        <TabItem title={t("tabs.source")}>
          {props.article != null ? (
            <div className="flex flex-col gap-6">
              <SourceOriginal article={props.article.original} source={props.source} />
              {props.article.relevance != null ? (
                <RelevancePanel relevance={props.article.relevance} />
              ) : null}
              <ScoreFeedback articleId={props.article.original.id} locale={props.locale} />
            </div>
          ) : (
            <p className="text-sm text-gray-500">{t("noSource")}</p>
          )}
        </TabItem>
      </Tabs>

      <DraftFeedback
        postId={props.post.id}
        pristineBody={pristineBody.current}
        currentBody={body}
        locale={props.locale}
      />
    </div>
  );
};
