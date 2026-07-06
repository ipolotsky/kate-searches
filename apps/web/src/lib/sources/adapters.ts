// Описание адаптера источника из /internal/adapters (config_schema — JSON-схема без секретов).

export interface JsonSchemaProperty {
  type?: string | string[];
  title?: string;
  description?: string;
  default?: unknown;
  enum?: unknown[];
  anyOf?: JsonSchemaProperty[];
  items?: JsonSchemaProperty;
  minimum?: number;
  maximum?: number;
}

export interface AdapterConfigSchema {
  type?: string;
  title?: string;
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
}

export interface AdapterDescriptor {
  type: string;
  capabilities: Record<string, unknown>;
  config_schema: AdapterConfigSchema;
}

export interface SourceTestSample {
  title: string | null;
  url: string;
  canonical_url?: string | null;
  published_at: string | null;
  is_novel: boolean;
  language: string | null;
  has_body: boolean;
  body_preview: string;
}

export interface SourceTestResponse {
  ok: boolean;
  supported?: boolean;
  error?: string | null;
  detail?: string;
  capabilities?: Record<string, unknown>;
  cursor_kind?: string;
  stats?: Record<string, number>;
  warnings?: string[];
  sample?: SourceTestSample[];
  supported_types?: string[];
}

export type FieldKind = "boolean" | "number" | "select" | "string";

// Определяет вид инпута из JSON-схемы свойства (anyOf [string,null] -> string и т.д.).
export const fieldKind = (property: JsonSchemaProperty): FieldKind => {
  if (Array.isArray(property.enum) && property.enum.length > 0) {
    return "select";
  }
  const types = collectTypes(property);
  if (types.includes("boolean")) {
    return "boolean";
  }
  if (types.includes("integer") || types.includes("number")) {
    return "number";
  }
  return "string";
};

const collectTypes = (property: JsonSchemaProperty): string[] => {
  const direct = Array.isArray(property.type)
    ? property.type
    : property.type != null
      ? [property.type]
      : [];
  const nested = (property.anyOf ?? []).flatMap((x) =>
    Array.isArray(x.type) ? x.type : x.type != null ? [x.type] : [],
  );
  return [...direct, ...nested];
};
