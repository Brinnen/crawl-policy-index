import { COUNTRY_LABELS, LANGUAGE_LABELS, VERTICAL_LABELS } from "./labels";

export type LookupPack = {
  named?: [string, string, string][];
  blanket?: [string, string][];
  sites?: [string, string, string, string][];
};

export type Verdict = "BLOCKED" | "ALLOWED" | "PARTIAL" | "BLANKET" | "DEFAULT";

export type FaceBot = {
  slug: string;
  short: string;
  line: string;
};

export type BotChip = FaceBot & {
  verdict: Verdict;
  label: string;
};

export type ExtraBot = {
  slug: string;
  token: string;
  operator: string;
  purpose: string;
  verdict: Verdict;
  label: string;
};

export type SiteView = {
  domain: string;
  onPanel: boolean;
  headline: string;
  language: string;
  country: string;
  category: string;
  blanket: string;
  bots: BotChip[];
  extras: ExtraBot[];
};

export type AgentMeta = {
  slug: string;
  token: string;
  operator: string;
  purpose: string;
};

export const FACE_BOTS: FaceBot[] = [
  { slug: "openai-gptbot", short: "GPTBot", line: "OpenAI's training crawler" },
  { slug: "anthropic-claudebot", short: "ClaudeBot", line: "Anthropic's training crawler" },
  { slug: "google-extended", short: "Google-Extended", line: "Google's Gemini opt-out" },
  { slug: "perplexity-bot", short: "PerplexityBot", line: "Perplexity's crawler" },
  { slug: "openai-chatgpt-user", short: "ChatGPT-User", line: "ChatGPT when a person asks" },
  { slug: "google-googlebot", short: "Googlebot", line: "Google Search" },
];

export const FAMOUS_SITES = [
  "nytimes.com",
  "wikipedia.org",
  "instagram.com",
  "amazon.com",
  "reddit.com",
  "bbc.com",
  "theguardian.com",
  "google.com",
  "youtube.com",
  "netflix.com",
  "github.com",
  "svt.se",
  "ebay.com",
  "apple.com",
  "tiktok.com",
  "weather.com",
];

const BOT_LINES: Record<string, string> = Object.fromEntries(
  FACE_BOTS.map((bot) => [bot.slug, bot.line]),
);

BOT_LINES["commoncrawl-ccbot"] = "Common Crawl";
BOT_LINES["openai-searchbot"] = "OpenAI's search crawler";
BOT_LINES["anthropic-claude-user"] = "Claude when a person asks";
BOT_LINES["anthropic-claude-searchbot"] = "Claude's search crawler";
BOT_LINES["meta-externalagent"] = "Meta's training crawler";
BOT_LINES["apple-applebot-extended"] = "Apple's AI opt-out";
BOT_LINES["wildcard-star"] = "every crawler";
BOT_LINES["amazon-amazonbot"] = "Amazon's crawler";
BOT_LINES["microsoft-bingbot"] = "Bing";
BOT_LINES["imagesift-bot"] = "ImageSift";

export function normalizeDomain(raw: string): string {
  let host = (raw || "").trim().toLowerCase();
  host = host.replace(/^https?:\/\//, "");
  host = host.split("/")[0] || "";
  host = host.split("?")[0] || "";
  host = host.split("#")[0] || "";
  host = host.replace(/\.$/, "");
  if (host.startsWith("www.")) host = host.slice(4);
  return host;
}

export function verdictLabel(verdict: Verdict): string {
  if (verdict === "BLOCKED" || verdict === "BLANKET") return "Blocked";
  if (verdict === "ALLOWED") return "Allowed";
  if (verdict === "PARTIAL") return "Mixed";
  return "Didn't say";
}

export function botLine(slug: string, fallback?: string): string {
  return BOT_LINES[slug] || fallback || slug;
}

export function andList(items: string[], max = 3): string {
  const trimmed =
    items.length > max
      ? [...items.slice(0, max - 1), `${items.length - (max - 1)} other AI crawlers`]
      : items;
  if (trimmed.length === 0) return "";
  if (trimmed.length === 1) return trimmed[0];
  if (trimmed.length === 2) return `${trimmed[0]} and ${trimmed[1]}`;
  return `${trimmed.slice(0, -1).join(", ")}, and ${trimmed[trimmed.length - 1]}`;
}

export function typeLabel(category: string): string {
  if (!category || category === "other") return "";
  return VERTICAL_LABELS[category] || category;
}

export function countryLabel(code: string): string {
  if (!code) return "";
  return COUNTRY_LABELS[code] || code;
}

export function languageLabel(code: string): string {
  if (!code) return "";
  return LANGUAGE_LABELS[code] || code;
}

export function metaLine(view: Pick<SiteView, "category" | "country" | "language">): string {
  return [typeLabel(view.category), countryLabel(view.country), languageLabel(view.language)]
    .filter(Boolean)
    .join(" · ");
}

export function changeSentence(kind: string, domain: string, agentSlug: string): string {
  const bot = agentSlug ? botLine(agentSlug, agentSlug) : "";
  if (kind === "blocked") {
    return bot ? `${domain} started blocking ${bot}.` : `${domain} started blocking crawlers.`;
  }
  if (kind === "unblocked") {
    return bot ? `${domain} let ${bot} back in.` : `${domain} let crawlers back in.`;
  }
  if (kind === "tightened") {
    return bot ? `${domain} tightened the rules for ${bot}.` : `${domain} tightened its crawl rules.`;
  }
  if (kind === "loosened") {
    return bot ? `${domain} loosened the rules for ${bot}.` : `${domain} loosened its crawl rules.`;
  }
  if (kind === "agent_named") {
    return bot ? `${domain} named ${bot} in its crawl rules.` : `${domain} named a crawler in its rules.`;
  }
  if (kind === "first_seen") {
    return bot ? `${domain} showed up with a rule for ${bot}.` : `${domain} showed up on the list.`;
  }
  return bot ? `${domain} changed its rule for ${bot}.` : `${domain} changed its crawl rules.`;
}

export function verdictFor(
  domain: string,
  slug: string,
  namedBy: Map<string, Map<string, string>>,
  blanketBy: Map<string, string>,
): Verdict {
  const named = namedBy.get(domain)?.get(slug);
  if (named === "BLOCKED" || named === "ALLOWED" || named === "PARTIAL") return named;
  const star = blanketBy.get(domain);
  if (star === "BLOCKED") return "BLANKET";
  if (star === "PARTIAL") return "PARTIAL";
  return "DEFAULT";
}

function indexPack(pack: LookupPack) {
  const namedBy = new Map<string, Map<string, string>>();
  for (const [domain, slug, state] of pack.named || []) {
    if (!namedBy.has(domain)) namedBy.set(domain, new Map());
    namedBy.get(domain)!.set(slug, state);
  }
  const blanketBy = new Map<string, string>();
  for (const [domain, state] of pack.blanket || []) {
    blanketBy.set(domain, state || "BLOCKED");
  }
  const siteBy = new Map<string, [string, string, string]>();
  for (const row of pack.sites || []) {
    if (!row || !row[0]) continue;
    siteBy.set(row[0], [row[1] || "", row[2] || "", row[3] || "other"]);
  }
  return { namedBy, blanketBy, siteBy };
}

function headlineFor(domain: string, bots: BotChip[], blanket: string): string {
  const blocked = bots
    .filter((bot) => bot.verdict === "BLOCKED" || bot.verdict === "BLANKET")
    .map((bot) => bot.line);
  const allowed = bots.filter((bot) => bot.verdict === "ALLOWED").map((bot) => bot.line);
  const mixed = bots.filter((bot) => bot.verdict === "PARTIAL").map((bot) => bot.line);
  if (blanket === "BLOCKED" && blocked.length >= 3) {
    return `${domain} told every crawler to stay out.`;
  }
  const parts: string[] = [];
  if (blocked.length) parts.push(`blocks ${andList(blocked)}`);
  if (mixed.length && !blocked.length) parts.push(`has mixed rules for ${andList(mixed)}`);
  else if (mixed.length) parts.push(`mixed rules for ${andList(mixed)}`);
  if (allowed.length) {
    const allowBit = `still allows ${andList(allowed)}`;
    if (parts.length) return `${domain} ${parts[0]}. It ${allowBit}.`;
    return `${domain} named a yes for ${andList(allowed)}.`;
  }
  if (parts.length) return `${domain} ${parts.join(", and ")}.`;
  return `${domain} did not name the main AI crawlers. By default, they may crawl.`;
}

export function buildSiteView(
  domain: string,
  pack: LookupPack,
  agents: AgentMeta[] = [],
): SiteView | null {
  const host = normalizeDomain(domain);
  if (!host) return null;
  const { namedBy, blanketBy, siteBy } = indexPack(pack);
  const site = siteBy.get(host);
  const named = namedBy.get(host);
  const blanket = blanketBy.get(host) || "";
  const onPanel = Boolean(site || named || blanket);
  if (!onPanel) return null;
  const [language, country, category] = site || ["", "", "other"];
  const bots: BotChip[] = FACE_BOTS.map((bot) => {
    const verdict = verdictFor(host, bot.slug, namedBy, blanketBy);
    return { ...bot, verdict, label: verdictLabel(verdict) };
  });
  const face = new Set(FACE_BOTS.map((bot) => bot.slug));
  const metaBy = new Map(agents.map((agent) => [agent.slug, agent]));
  const extras: ExtraBot[] = [];
  for (const [slug, state] of named || []) {
    if (face.has(slug)) continue;
    const meta = metaBy.get(slug);
    const verdict = (state as Verdict) || "DEFAULT";
    extras.push({
      slug,
      token: meta?.token || slug,
      operator: meta?.operator || "",
      purpose: meta?.purpose || "",
      verdict,
      label: verdictLabel(verdict),
    });
  }
  extras.sort((a, b) => a.token.localeCompare(b.token));
  return {
    domain: host,
    onPanel: true,
    headline: headlineFor(host, bots, blanket),
    language,
    country,
    category,
    blanket,
    bots,
    extras,
  };
}
