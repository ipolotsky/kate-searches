import { createTwoFilesPatch } from "diff";

// Компактный сигнал редактуры: unified-патч draft -> final. Высший сигнал для дообучения
// брендового голоса. Чистая функция — тестируется юнитом.
export interface EditedDiff {
  engine: "jsdiff";
  format: "unified";
  patch: string;
  original_len: number;
  edited_len: number;
}

export const buildEditedDiff = (original: string, edited: string): EditedDiff => {
  const patch = createTwoFilesPatch("draft", "final", original, edited, "", "");
  return {
    engine: "jsdiff",
    format: "unified",
    patch,
    original_len: original.length,
    edited_len: edited.length,
  };
};

export const hasChanges = (original: string, edited: string): boolean => original !== edited;
