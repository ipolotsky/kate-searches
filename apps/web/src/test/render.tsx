import { render, type RenderResult } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactElement } from "react";
import { ToastProvider } from "@/components/ui/ToastProvider";
import messages from "../../messages/en.json";

// Обёртка тест-рендера: i18n (en) + Toast-контекст.
export const renderWithProviders = (ui: ReactElement): RenderResult =>
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ToastProvider>{ui}</ToastProvider>
    </NextIntlClientProvider>,
  );
