import type { APIRoute } from "astro";
import { isSubscribed } from "../../lib/access";

export const GET: APIRoute = async (context) => {
  const { userId } = context.locals.auth();
  if (!userId) return new Response("Unauthorized", { status: 401 });

  const user = await context.locals.currentUser();
  if (!isSubscribed(user)) return new Response("Payment required", { status: 402 });

  const lookupUrl = import.meta.env.CPI_LOOKUP_URL || "http://178.128.255.20/snapshot/lookup.json";
  const token = import.meta.env.CPI_LOOKUP_TOKEN;
  const headers: Record<string, string> = {};
  if (token) headers["x-cpi-lookup-token"] = token;

  const res = await fetch(lookupUrl, {
    headers,
    signal: AbortSignal.timeout(25000),
  });
  if (!res.ok) {
    return new Response("lookup unavailable", { status: 502 });
  }
  const body = await res.text();
  return new Response(body, {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "private, max-age=60",
    },
  });
};
