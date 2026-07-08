"use client";

import { Badge, Button, Card } from "flowbite-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { openBillingPortal, startCheckout } from "@/app/[locale]/(app)/_actions/billing";
import { useToast } from "@/components/ui/ToastProvider";
import { formatUsd } from "@/lib/usage";

type PaidPlan = "starter" | "pro" | "agency";

interface PlanCard {
  plan: PaidPlan;
  price: number;
  sources: number | null;
  drafts: number | null;
}

interface BillingPanelProps {
  locale: string;
  plans: PlanCard[];
  status: string | null;
  trialDaysLeft: number | null;
  draftsUsed: number;
  trialDraftsLimit: number;
  hasSubscription: boolean;
  billingEnabled: boolean;
}

const errorKey = (code: string | undefined): string => {
  switch (code) {
    case "notConfigured":
      return "errorNotConfigured";
    case "billingDisabled":
      return "errorBillingDisabled";
    case "noCustomer":
      return "errorNoCustomer";
    default:
      return "errorGeneric";
  }
};

const statusKey = (status: string | null): string => {
  switch (status) {
    case "trialing":
      return "statusTrialing";
    case "active":
      return "statusActive";
    case "past_due":
      return "statusPastDue";
    default:
      return "statusNone";
  }
};

export const BillingPanel: React.FC<BillingPanelProps> = (props) => {
  const t = useTranslations("billing");
  const toast = useToast();
  const [loading, setLoading] = useState<string | null>(null);

  const planLabel = (plan: PaidPlan): string =>
    ({ starter: t("planStarter"), pro: t("planPro"), agency: t("planAgency") })[plan];

  const onCheckout = async (plan: PaidPlan): Promise<void> => {
    setLoading(plan);
    const result = await startCheckout(plan, props.locale);
    if (result.ok && result.url != null) {
      window.location.assign(result.url);
      return;
    }
    setLoading(null);
    toast.show(t(errorKey(result.code)), "error");
  };

  const onPortal = async (): Promise<void> => {
    setLoading("portal");
    const result = await openBillingPortal(props.locale);
    if (result.ok && result.url != null) {
      window.location.assign(result.url);
      return;
    }
    setLoading(null);
    toast.show(t(errorKey(result.code)), "error");
  };

  const statusColor =
    props.status === "active" ? "success" : props.status === "past_due" ? "warning" : "info";

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500">{t("status")}</span>
            <Badge color={statusColor}>{t(statusKey(props.status))}</Badge>
          </div>
          {props.hasSubscription ? (
            <Button color="light" onClick={onPortal} disabled={loading != null}>
              {loading === "portal" ? t("redirecting") : t("manageBilling")}
            </Button>
          ) : null}
        </div>
        {props.status === "trialing" ? (
          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
            {props.trialDaysLeft != null ? (
              <span>{t("trialDaysLeft", { days: props.trialDaysLeft })}</span>
            ) : null}
            <span>
              {t("trialDraftsUsed", { used: props.draftsUsed, limit: props.trialDraftsLimit })}
            </span>
          </div>
        ) : null}
      </Card>

      {!props.billingEnabled ? (
        <p className="text-sm text-gray-500">{t("billingDisabled")}</p>
      ) : !props.hasSubscription ? (
        <>
          <p className="text-sm text-gray-500">{t("trialNote")}</p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {props.plans.map((card) => (
              <Card key={card.plan}>
                <div className="flex items-baseline justify-between">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {planLabel(card.plan)}
                  </h3>
                  <span className="text-sm text-gray-500">
                    {formatUsd(card.price)}
                    {t("perMonth")}
                  </span>
                </div>
                <div className="flex flex-col gap-1 text-sm text-gray-500">
                  <span>
                    {t("sourcesLabel")}: {card.sources ?? "—"}
                  </span>
                  <span>
                    {t("draftsLabel")}: {card.drafts ?? "—"}
                  </span>
                </div>
                <Button
                  color="blue"
                  onClick={() => onCheckout(card.plan)}
                  disabled={loading != null}
                >
                  {loading === card.plan ? t("redirecting") : t("startTrial")}
                </Button>
              </Card>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
};
