export const dynamic = "force-dynamic";

const apiBase = (): string => process.env.API_BASE_URL ?? "http://localhost:8000";

// Readiness: web считается здоровым, только если дотягивается до API. Раньше ручка возвращала
// литеральный 200, поэтому healthcheck-gated rollout переключал трафик на web, который не может
// достучаться до бэкенда. 503 при недоступности API -> rollout не переключается.
export async function GET(): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 2000);
  try {
    const upstream = await fetch(`${apiBase()}/health`, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!upstream.ok) {
      return Response.json({ status: "unavailable", api: upstream.status }, { status: 503 });
    }
    return Response.json({ status: "ok" });
  } catch {
    return Response.json({ status: "unavailable", api: "unreachable" }, { status: 503 });
  } finally {
    clearTimeout(timer);
  }
}
