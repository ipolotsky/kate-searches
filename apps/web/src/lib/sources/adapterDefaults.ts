import type { AdapterDescriptor } from "./adapters";

// Fallback-описание адаптеров, если /internal/adapters недоступен (API не задеплоен).
// Зеркалит config_model адаптеров rss/sitemap/scraper.
export const ADAPTER_DEFAULTS: AdapterDescriptor[] = [
  {
    type: "rss",
    capabilities: { provides_full_text: false, supports_incremental: true },
    config_schema: {
      type: "object",
      properties: {
        language: { anyOf: [{ type: "string" }, { type: "null" }], default: null, title: "Language" },
        full_text_fetch: { type: "boolean", default: true, title: "Full text fetch" },
        novelty_days: { type: "integer", default: 0, title: "Novelty days" },
      },
    },
  },
  {
    type: "sitemap",
    capabilities: { provides_full_text: false, supports_incremental: true },
    config_schema: {
      type: "object",
      properties: {
        language: { anyOf: [{ type: "string" }, { type: "null" }], default: null, title: "Language" },
        max_urls: { type: "integer", default: 200, title: "Max urls" },
        follow_index: { type: "boolean", default: true, title: "Follow index" },
        novelty_days: { type: "integer", default: 0, title: "Novelty days" },
      },
    },
  },
  {
    type: "scraper",
    capabilities: { provides_full_text: true, needs_javascript: false },
    config_schema: {
      type: "object",
      properties: {
        render_js: { type: "boolean", default: false, title: "Render JS" },
        language: { anyOf: [{ type: "string" }, { type: "null" }], default: null, title: "Language" },
        novelty_days: { type: "integer", default: 0, title: "Novelty days" },
      },
    },
  },
];
