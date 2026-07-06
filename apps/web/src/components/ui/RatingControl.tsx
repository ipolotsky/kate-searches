"use client";

import { Button } from "flowbite-react";

interface RatingControlProps {
  value: number | null;
  onChange: (value: number) => void;
  upLabel: string;
  downLabel: string;
}

// Простой сигнал -1 / +1 (схема feedback.rating допускает и 1..5, здесь бинарный палец).
export const RatingControl: React.FC<RatingControlProps> = (props) => (
  <div className="flex gap-2">
    <Button
      size="sm"
      color={props.value === 1 ? "green" : "light"}
      aria-pressed={props.value === 1}
      onClick={() => props.onChange(1)}
    >
      {props.upLabel}
    </Button>
    <Button
      size="sm"
      color={props.value === -1 ? "failure" : "light"}
      aria-pressed={props.value === -1}
      onClick={() => props.onChange(-1)}
    >
      {props.downLabel}
    </Button>
  </div>
);
