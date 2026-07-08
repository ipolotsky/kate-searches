import type { NextRequest } from "next/server";
import { postInternal } from "@/lib/api/internal";

export const dynamic = "force-dynamic";

const page = (title: string, message: string): string =>
  `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title></head><body style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#f3f4f6;margin:0;padding:48px 24px;text-align:center;color:#374151"><h2 style="color:#111827">${title}</h2><p>${message}</p></body></html>`;

const unsubscribe = async (token: string | null): Promise<boolean> => {
  if (token == null || token.length === 0) {
    return false;
  }
  const result = await postInternal<{ ok?: boolean }>("/internal/email/unsubscribe", { token });
  return result.ok && result.data.ok === true;
};

// One-click отписка (List-Unsubscribe-Post): почтовый клиент POST-ит на URL из заголовка письма.
export async function POST(request: NextRequest): Promise<Response> {
  await unsubscribe(new URL(request.url).searchParams.get("token"));
  return new Response("Unsubscribed", { status: 200 });
}

// Человекочитаемая страница отписки (клик по ссылке в письме).
export async function GET(request: NextRequest): Promise<Response> {
  const ok = await unsubscribe(new URL(request.url).searchParams.get("token"));
  const html = ok
    ? page("You're unsubscribed", "You will no longer receive digest emails.")
    : page("Link expired", "This unsubscribe link is invalid or has already been used.");
  return new Response(html, {
    status: ok ? 200 : 404,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}
