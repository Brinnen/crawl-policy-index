import lab from "../data/lab.json";
import preview from "../data/preview.json";
import { buildSiteView, type AgentMeta, type LookupPack, type SiteView, normalizeDomain } from "./story";

type Cache = { at: number; pack: LookupPack };

let cache: Cache | null = null;
const TTL_MS = 60_000;

const AGENTS: AgentMeta[] = (lab.by_agent ?? []).map((row) => ({
  slug: row.slug,
  token: row.token,
  operator: row.operator,
  purpose: row.purpose,
}));

function asPack(value: unknown): LookupPack {
  const pack = (value || {}) as LookupPack;
  return {
    named: Array.isArray(pack.named) ? pack.named : [],
    blanket: Array.isArray(pack.blanket) ? pack.blanket : [],
    sites: Array.isArray(pack.sites) ? pack.sites : [],
  };
}

export function previewPack(): LookupPack {
  return asPack(preview);
}

export function agents(): AgentMeta[] {
  return AGENTS;
}

export async function loadLookupPack(): Promise<LookupPack> {
  if (cache && Date.now() - cache.at < TTL_MS) return cache.pack;
  const lookupUrl = import.meta.env.CPI_LOOKUP_URL || "http://178.128.255.20/snapshot/lookup.json";
  const token = import.meta.env.CPI_LOOKUP_TOKEN;
  const headers: Record<string, string> = {};
  if (token) headers["x-cpi-lookup-token"] = token;
  try {
    const res = await fetch(lookupUrl, {
      headers,
      signal: AbortSignal.timeout(20000),
    });
    if (!res.ok) throw new Error(String(res.status));
    const pack = asPack(await res.json());
    if (!pack.sites?.length) throw new Error("empty lookup");
    cache = { at: Date.now(), pack };
    return pack;
  } catch {
    return previewPack();
  }
}

export async function loadSiteView(domain: string): Promise<SiteView | null> {
  const host = normalizeDomain(domain);
  if (!host) return null;
  const previewView = buildSiteView(host, previewPack(), AGENTS);
  if (previewView) return previewView;
  try {
    const pack = await loadLookupPack();
    return buildSiteView(host, pack, AGENTS);
  } catch {
    return null;
  }
}
