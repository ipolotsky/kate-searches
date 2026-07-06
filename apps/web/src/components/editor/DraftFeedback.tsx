"use client";

import { Button, Textarea } from "flowbite-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { submitDraftFeedback } from "@/app/[locale]/(app)/_actions/feedback";
import { RatingControl } from "@/components/ui/RatingControl";
import { useToast } from "@/components/ui/ToastProvider";
import { buildEditedDiff, hasChanges } from "@/lib/feedback/diff";

interface DraftFeedbackProps {
  postId: string;
  pristineBody: string;
  currentBody: string;
  locale: string;
}

export const DraftFeedback: React.FC<DraftFeedbackProps> = (props) => {
  const t = useTranslations("feedback");
  const toast = useToast();
  const [rating, setRating] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const changed = hasChanges(props.pristineBody, props.currentBody);
  const canSubmit = rating != null || comment.trim().length > 0 || changed;

  const submit = async (): Promise<void> => {
    if (!canSubmit) {
      return;
    }
    setLoading(true);
    const editedDiff = changed ? buildEditedDiff(props.pristineBody, props.currentBody) : null;
    const result = await submitDraftFeedback(
      { postId: props.postId, rating, comment, editedDiff },
      props.locale,
    );
    setLoading(false);
    if (result.ok) {
      setDone(true);
      toast.show(t("thanks"), "success");
    } else {
      toast.show(t("failed"), "error");
    }
  };

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-gray-200 p-4 dark:border-gray-700">
      <div>
        <h4 className="text-sm font-semibold text-gray-900 dark:text-white">{t("draft.title")}</h4>
        <p className="text-sm text-gray-500">{t("draft.hint")}</p>
      </div>
      {done ? (
        <p className="text-sm text-green-600 dark:text-green-400">{t("thanks")}</p>
      ) : (
        <>
          <RatingControl
            value={rating}
            onChange={setRating}
            upLabel={t("up")}
            downLabel={t("down")}
          />
          {changed ? (
            <p className="text-xs text-green-600 dark:text-green-400">{t("draft.includesEdits")}</p>
          ) : null}
          <Textarea
            rows={3}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder={t("commentPlaceholder")}
            aria-label={t("commentPlaceholder")}
          />
          <div>
            <Button size="sm" color="blue" disabled={!canSubmit || loading} onClick={submit}>
              {t("submit")}
            </Button>
          </div>
        </>
      )}
    </div>
  );
};
