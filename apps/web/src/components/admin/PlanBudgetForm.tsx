"use client";

import { Button, Label, Select, TextInput } from "flowbite-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { updateTenantPlan } from "@/app/[locale]/(app)/_actions/admin";
import { useToast } from "@/components/ui/ToastProvider";
import { PLANS, PLAN_CATALOG, type Plan } from "@/lib/plans";

interface PlanBudgetFormProps {
  tenantId: string;
  locale: string;
  initialPlan: string;
  initialBudget: number;
  initialThreshold: number;
}

export const PlanBudgetForm: React.FC<PlanBudgetFormProps> = (props) => {
  const t = useTranslations("admin.form");
  const toast = useToast();

  const [plan, setPlan] = useState(props.initialPlan);
  const [budget, setBudget] = useState(props.initialBudget);
  const [threshold, setThreshold] = useState(props.initialThreshold);
  const [loading, setLoading] = useState(false);

  const changePlan = (value: string): void => {
    setPlan(value);
    // Подставить дефолтный бюджет выбранного тарифа; админ может переопределить.
    const spec = PLAN_CATALOG[value as Plan];
    if (spec != null) {
      setBudget(spec.usableBudget);
    }
  };

  const submit = async (): Promise<void> => {
    setLoading(true);
    const result = await updateTenantPlan(
      { tenantId: props.tenantId, plan, budget, upsellThresholdPct: threshold },
      props.locale,
    );
    setLoading(false);
    toast.show(result.ok ? t("saved") : t("failed"), result.ok ? "success" : "error");
  };

  return (
    <div className="flex max-w-sm flex-col gap-4">
      <div>
        <Label htmlFor="tenant-plan" className="mb-1 block">
          {t("plan")}
        </Label>
        <Select id="tenant-plan" value={plan} onChange={(event) => changePlan(event.target.value)}>
          {PLANS.map((x) => (
            <option key={x} value={x}>
              {x}
            </option>
          ))}
        </Select>
      </div>

      <div>
        <Label htmlFor="tenant-budget" className="mb-1 block">
          {t("budget")}
        </Label>
        <TextInput
          id="tenant-budget"
          type="number"
          min={0}
          step={0.01}
          value={budget}
          onChange={(event) => setBudget(Number(event.target.value))}
        />
        <p className="mt-1 text-xs text-gray-400">{t("budgetHint")}</p>
      </div>

      <div>
        <Label htmlFor="tenant-threshold" className="mb-1 block">
          {t("threshold")}
        </Label>
        <TextInput
          id="tenant-threshold"
          type="number"
          min={0}
          max={100}
          value={threshold}
          onChange={(event) => setThreshold(Number(event.target.value))}
        />
      </div>

      <div>
        <Button color="blue" onClick={submit} disabled={loading}>
          {t("save")}
        </Button>
      </div>
    </div>
  );
};
