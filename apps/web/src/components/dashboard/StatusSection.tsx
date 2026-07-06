"use client";

import { useState } from "react";

interface StatusSectionProps {
  title: string;
  count: number;
  defaultOpen: boolean;
  children: React.ReactNode;
}

export const StatusSection: React.FC<StatusSectionProps> = (props) => {
  const [open, setOpen] = useState(props.defaultOpen);

  return (
    <section className="mb-4">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((x) => !x)}
        className="flex w-full items-center gap-2 rounded-lg px-1 py-2 text-left"
      >
        <svg
          className={`h-4 w-4 shrink-0 text-gray-400 transition-transform ${open ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
          aria-hidden
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
        </svg>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{props.title}</h2>
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">
          {props.count}
        </span>
      </button>
      {open ? <div className="mt-2">{props.children}</div> : null}
    </section>
  );
};
