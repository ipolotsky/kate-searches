"use client";

import { Toast, ToastToggle } from "flowbite-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

type ToastVariant = "success" | "error" | "info";

interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
}

interface ToastApi {
  show: (message: string, variant?: ToastVariant) => void;
}

interface ToastProviderProps {
  children: React.ReactNode;
}

const ToastContext = createContext<ToastApi | null>(null);

const VARIANT_DOT: Record<ToastVariant, string> = {
  success: "bg-green-500",
  error: "bg-red-500",
  info: "bg-blue-500",
};

export const useToast = (): ToastApi => {
  const context = useContext(ToastContext);
  if (context == null) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
};

export const ToastProvider: React.FC<ToastProviderProps> = (props) => {
  const [items, setItems] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const show = useCallback(
    (message: string, variant: ToastVariant = "info") => {
      counter.current += 1;
      const id = counter.current;
      setItems((prev) => [...prev, { id, message, variant }]);
      setTimeout(() => {
        dismiss(id);
      }, 4500);
    },
    [dismiss],
  );

  const api = useMemo<ToastApi>(() => ({ show }), [show]);

  const renderToast = (x: ToastItem): React.ReactNode => (
    <Toast key={x.id}>
      <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${VARIANT_DOT[x.variant]}`} />
      <div className="ml-3 text-sm font-normal">{x.message}</div>
      <ToastToggle onClick={() => dismiss(x.id)} />
    </Toast>
  );

  return (
    <ToastContext.Provider value={api}>
      {props.children}
      {/* Ошибки — assertive (сообщают о провале действия сразу), остальное — polite. */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        <div className="flex flex-col gap-2" role="status" aria-live="polite">
          {items.filter((x) => x.variant !== "error").map(renderToast)}
        </div>
        <div className="flex flex-col gap-2" role="alert" aria-live="assertive">
          {items.filter((x) => x.variant === "error").map(renderToast)}
        </div>
      </div>
    </ToastContext.Provider>
  );
};
