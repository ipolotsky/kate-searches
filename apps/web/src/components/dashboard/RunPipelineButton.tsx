"use client";

import { Button, Spinner } from "flowbite-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { runPipeline } from "@/app/[locale]/(app)/_actions/pipeline";
import { useToast } from "@/components/ui/ToastProvider";
import { RefreshIcon } from "@/components/ui/icons";

interface RunPipelineButtonProps {
  locale: string;
}

export const RunPipelineButton: React.FC<RunPipelineButtonProps> = (props) => {
  const t = useTranslations("dashboard");
  const toast = useToast();
  const [loading, setLoading] = useState(false);

  const run = async (): Promise<void> => {
    setLoading(true);
    const result = await runPipeline(props.locale);
    setLoading(false);
    if (result.ok) {
      toast.show(t("runPipeline.queued"), "success");
    } else if (result.code === "alreadyRan") {
      toast.show(t("runPipeline.alreadyRan"), "info");
    } else {
      toast.show(t("runPipeline.failed"), "error");
    }
  };

  return (
    <Button color="light" size="sm" onClick={run} disabled={loading}>
      {loading ? (
        <Spinner size="sm" className="mr-2" />
      ) : (
        <RefreshIcon className="mr-2 h-4 w-4" />
      )}
      {t("runPipeline.action")}
    </Button>
  );
};
