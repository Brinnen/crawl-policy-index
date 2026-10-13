import type { APIRoute } from "astro";
import { loadSiteView } from "../../lib/lookupPack";
import { normalizeDomain } from "../../lib/story";

export const GET: APIRoute = async ({ url }) => {
  const host = normalizeDomain(url.searchParams.get("domain") || "");
  if (!host) {
    return new Response(JSON.stringify({ error: "missing domain" }), {
      status: 400,
      headers: { "content-type": "application/json; charset=utf-8" },
    });
  }
  const view = await loadSiteView(host);
  if (!view) {
    return new Response(
      JSON.stringify({
        error: "not_on_panel",
        domain: host,
        headline: `${host} is not on the list we watch.`,
      }),
      {
        status: 404,
        headers: {
          "content-type": "application/json; charset=utf-8",
          "cache-control": "public, max-age=60",
        },
      },
    );
  }
  return new Response(JSON.stringify(view), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "public, max-age=60",
    },
  });
};
