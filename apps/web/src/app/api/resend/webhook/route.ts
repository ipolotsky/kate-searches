import type { NextRequest } from "next/server";
import { postInternal } from "@/lib/api/internal";

export const dynamic = "force-dynamic";

// Вебхук Resend приземляется на web (единственный внешне доступный сервис) и проксируется на
// Python-сервис, где проверяется Svix-подпись и пишется suppression. Пересылаем СЫРОЕ тело и
// svix-заголовки без изменений, иначе подпись не сойдётся.
export async function POST(request: NextRequest): Promise<Response> {
  const payload = await request.text();
  const headers = {
    "svix-id": request.headers.get("svix-id") ?? "",
    "svix-timestamp": request.headers.get("svix-timestamp") ?? "",
    "svix-signature": request.headers.get("svix-signature") ?? "",
  };
  const result = await postInternal<{ ok?: boolean }>("/internal/email/webhook", {
    payload,
    headers,
  });
  if (!result.ok) {
    return new Response("upstream error", { status: 502 });
  }
  return result.data.ok
    ? new Response("ok", { status: 200 })
    : new Response("rejected", { status: 400 });
}
