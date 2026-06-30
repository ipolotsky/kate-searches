import { describe, expect, it } from "vitest";
import en from "../messages/en.json";
import ru from "../messages/ru.json";

// Все локали должны иметь идентичный набор ключей (защита от забытых переводов).
function keyPaths(obj: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) => {
    const path = prefix ? `${prefix}.${k}` : k;
    return v && typeof v === "object"
      ? keyPaths(v as Record<string, unknown>, path)
      : [path];
  });
}

describe("i18n messages", () => {
  it("en and ru have the same key set", () => {
    const enKeys = keyPaths(en).sort();
    const ruKeys = keyPaths(ru).sort();
    expect(ruKeys).toEqual(enKeys);
  });

  it("no empty translations", () => {
    for (const messages of [en, ru]) {
      const values = keyPaths(messages).map((p) =>
        p.split(".").reduce<unknown>((o, k) => (o as Record<string, unknown>)[k], messages),
      );
      expect(values.every((v) => typeof v === "string" && v.length > 0)).toBe(true);
    }
  });
});
