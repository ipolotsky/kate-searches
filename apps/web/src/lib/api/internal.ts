// BFF-мост к FastAPI (/internal/*). Сервис смонтирован без CORS и без auth и берёт
// tenant_id как обычное поле тела, поэтому браузер напрямую звать нельзя — только с сервера,
// с tenant_id, резолвленным через getUserAndTenant(). Сырые ошибки API наружу не текут:
// возвращаем {ok:false, code}, код мапится в i18n.

export interface InternalOk<T> {
  ok: true;
  data: T;
}

export interface InternalError {
  ok: false;
  code: string;
}

export type InternalResult<T> = InternalOk<T> | InternalError;

const baseUrl = (): string => process.env.API_BASE_URL ?? "http://localhost:8000";

interface RequestOptions {
  timeoutMs?: number;
}

const attempt = async <T>(
  path: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<InternalResult<T>> => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${baseUrl()}${path}`, {
      ...init,
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) {
      return { ok: false, code: "apiError" };
    }
    const data = (await response.json()) as T;
    return { ok: true, data };
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return { ok: false, code: "timeout" };
    }
    return { ok: false, code: "networkError" };
  } finally {
    clearTimeout(timer);
  }
};

const request = async <T>(
  path: string,
  init: RequestInit,
  options: RequestOptions,
): Promise<InternalResult<T>> => {
  const timeoutMs = options.timeoutMs ?? 5000;
  const first = await attempt<T>(path, init, timeoutMs);
  // Один ретрай только на networkError: переживаем cutover api при docker rollout
  // (connection refused/reset — запрос почти всегда не дошёл до сервера, повтор безопасен).
  if (first.ok || first.code !== "networkError") {
    return first;
  }
  await new Promise<void>((x) => setTimeout(x, 300));
  return attempt<T>(path, init, timeoutMs);
};

export const postInternal = async <T = unknown>(
  path: string,
  body: unknown,
  options: RequestOptions = {},
): Promise<InternalResult<T>> =>
  request<T>(
    path,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
    options,
  );

export const getInternal = async <T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<InternalResult<T>> => request<T>(path, { method: "GET" }, options);
