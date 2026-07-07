"use client";

import {
  Button,
  Label,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeadCell,
  TableRow,
  TextInput,
} from "flowbite-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { grantPlatformAdmin, revokePlatformAdmin } from "@/app/[locale]/(app)/_actions/admin";
import { ArrowLeftIcon } from "@/components/ui/icons";
import { useToast } from "@/components/ui/ToastProvider";

export interface AdminRow {
  userId: string;
  email: string;
  createdAt: string;
}

interface PlatformAdminsManagerProps {
  rows: AdminRow[];
  currentUserId: string;
  locale: string;
}

const isoDate = (value: string): string => new Date(value).toISOString().slice(0, 10);

export const PlatformAdminsManager: React.FC<PlatformAdminsManagerProps> = (props) => {
  const t = useTranslations("admin.admins");
  const toast = useToast();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);

  const notify = (result: { ok: boolean; code?: string }, successKey: string): void => {
    if (result.ok) {
      toast.show(t(successKey), "success");
      router.refresh();
    } else {
      toast.show(t(`errors.${result.code ?? "failed"}`), "error");
    }
  };

  const grant = async (): Promise<void> => {
    setLoading(true);
    const result = await grantPlatformAdmin(email, props.locale);
    setLoading(false);
    if (result.ok) {
      setEmail("");
    }
    notify(result, "granted");
  };

  const revoke = async (userId: string): Promise<void> => {
    const result = await revokePlatformAdmin(userId, props.locale);
    notify(result, "revoked");
  };

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div>
        <Link
          href={`/${props.locale}/admin`}
          className="mb-2 inline-flex items-center gap-1 text-sm text-gray-500 hover:underline"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          {t("back")}
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t("title")}</h1>
        <p className="text-sm text-gray-500">{t("subtitle")}</p>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-0 flex-1">
          <Label htmlFor="grant-email" className="mb-1 block">
            {t("email")}
          </Label>
          <TextInput
            id="grant-email"
            type="email"
            placeholder={t("grantPlaceholder")}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <Button color="blue" onClick={grant} disabled={loading || email.trim().length === 0}>
          {t("grant")}
        </Button>
      </div>

      {props.rows.length === 0 ? (
        <p className="text-sm text-gray-500">{t("empty")}</p>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeadCell>{t("email")}</TableHeadCell>
                <TableHeadCell>{t("added")}</TableHeadCell>
                <TableHeadCell>
                  <span className="sr-only">{t("actions")}</span>
                </TableHeadCell>
              </TableRow>
            </TableHead>
            <TableBody className="divide-y">
              {props.rows.map((row) => (
                <TableRow key={row.userId} className="bg-white dark:bg-gray-800">
                  <TableCell className="font-medium text-gray-900 dark:text-white">
                    {row.email}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-gray-500">
                    {isoDate(row.createdAt)}
                  </TableCell>
                  <TableCell className="text-right">
                    {row.userId === props.currentUserId ? (
                      <span className="text-xs text-gray-400">{t("you")}</span>
                    ) : (
                      <Button size="xs" color="light" onClick={() => revoke(row.userId)}>
                        {t("remove")}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
};
