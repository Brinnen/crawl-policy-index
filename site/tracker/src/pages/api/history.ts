import type { APIRoute } from "astro";
import { isHistory } from "../../lib/access";

export const GET: APIRoute = async (context) => {
  let userId: string | null = null;
  try {
    userId = context.locals.auth?.()?.userId ?? null;
  } catch {
    userId = null;
  }
  if (!userId) return new Response("Unauthorized", { status: 401 });

  let user: { publicMetadata?: Record<string, unknown> } | null = null;
  try {
    user = (await context.locals.currentUser?.()) ?? null;
  } catch {
    user = null;
  }
  if (!isHistory(user)) return new Response("Payment required", { status: 402 });

  const historyUrl =
    import.meta.env.CPI_HISTORY_URL || "http://178.128.255.20/snapshot/events.json";
  const token = import.meta.env.CPI_LOOKUP_TOKEN;
  const headers: Record<string, string> = {};
  if (token) headers["x-cpi-lookup-token"] = token;

  const res = await fetch(historyUrl, {
    headers,
    signal: AbortSignal.timeout(25000),
  });
  if (!res.ok) {
    return new Response(JSON.stringify({ events: [] }), {
      headers: {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "private, max-age=60",
      },
    });
  }
  const body = await res.text();
  return new Response(body, {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "private, max-age=60",
    },
  });
};
