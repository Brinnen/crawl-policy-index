import { PURPOSE_LABELS, STATE_LABELS } from "../lib/labels";

export const SNAPSHOT_URL = "/snapshot/lab.json";
export const LOOKUP_URL = "/api/lookup";

export type LabRow = {
  domain?: string;
  state?: string;
  valid_from?: string;
  agent_slug?: string;
  token?: string;
  agent?: string;
  operator?: string;
  purpose?: string;
  kind?: string;
  group_key?: string;
};

export type LabAgent = {
  slug: string;
  token: string;
  agent: string;
  operator: string;
  purpose: string;
  named_block: number | null;
  named_allow: number | null;
  named_partial: number | null;
};

export type LabSnapshot = {
  generated_at: string;
  summary: Record<string, number | null>;
  by_agent?: LabAgent[];
  named?: LabRow[];
  blanket?: LabRow[];
};

declare global {
  interface Window {
    __CPI_LAB?: LabSnapshot;
  }
}

function fmt(n: number) {
  return n.toLocaleString("en-US");
}

function esc(value: string) {
  return value.replace(/[&<>"']/g, (ch) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch] || ch,
  );
}

function purpose(value: string | undefined) {
  if (!value) return "—";
  return PURPOSE_LABELS[value] || value.replaceAll("_", " ");
}

function applySummary(lab: LabSnapshot) {
  const s = lab.summary || {};
  if (s.panel_size != null) {
    const label = fmt(Number(s.panel_size));
    document.querySelectorAll("[data-panel-size]").forEach((el) => {
      el.textContent = label;
    });
  }
  document.querySelectorAll<HTMLElement>("[data-stat]").forEach((el) => {
    const key = el.dataset.stat;
    if (!key || s[key] == null) return;
    el.textContent = fmt(Number(s[key]));
  });
  const dateEl = document.querySelector("[data-exported-date]");
  if (dateEl && lab.generated_at) {
    dateEl.textContent = new Date(lab.generated_at).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    });
  }
  const chart = document.getElementById("cpi-gptbot-chart");
  if (chart) redrawChart(chart, s);
  applyHomeAgents(lab.by_agent || []);
}

function dash(n: number | null | undefined) {
  if (n === null || n === undefined) return "—";
  return fmt(n);
}

function applyHomeAgents(agents: LabAgent[]) {
  const body = document.querySelector("[data-home-agents]");
  if (!body || agents.length === 0) return;
  body.innerHTML = agents
    .map(
      (row) => `<tr>
        <td><a href="/data?agent=${encodeURIComponent(row.slug)}">${esc(row.token)}</a></td>
        <td>${esc(row.operator)}</td>
        <td>${esc(purpose(row.purpose))}</td>
        <td class="num">${dash(row.named_block)}</td>
        <td class="num">${dash(row.named_allow)}</td>
        <td class="num">${dash(row.named_partial)}</td>
      </tr>`,
    )
    .join("");
}

function pct(n: number, total: number) {
  if (total === 0) return "0%";
  return `${Math.round((n / total) * 100)}%`;
}

function redrawChart(root: HTMLElement, s: Record<string, number | null>) {
  const block = Number(s.gptbot_named_block || 0);
  const allow = Number(s.gptbot_named_allow || 0);
  const partial = Number(s.gptbot_named_partial || 0);
  const blanket = s.gptbot_blanket_block;
  const showBlanket = typeof blanket === "number";
  const blanketN = showBlanket ? Number(blanket) : 0;
  const realTotal = block + allow + partial + blanketN;
  const total = Math.max(realTotal, 1);
  const w = 920;
  const y = 14;
  const barH = 28;
  const segs = [
    { n: block, color: "var(--block)", show: true },
    { n: blanketN, color: "var(--blanket)", show: showBlanket },
    { n: allow, color: "var(--allow)", show: true },
    { n: partial, color: "var(--partial)", show: true },
  ].filter((seg) => seg.show);
  let cursor = 0;
  const rects = segs.map((seg) => {
    const width = realTotal === 0 ? 0 : (seg.n / total) * w;
    const rect = { x: cursor, width, color: seg.color };
    cursor += width;
    return rect;
  });
  const svg = root.querySelector("svg.chart");
  const g = svg?.querySelector("g");
  if (g) {
    g.innerHTML = rects
      .filter((rect) => rect.width > 0)
      .map(
        (rect) =>
          `<rect x="${rect.x}" y="${y}" width="${rect.width}" height="${barH}" fill="${rect.color}"></rect>`,
      )
      .join("");
  }
  const legend = root.querySelector(".legend");
  if (legend) {
    const blanketLabel = showBlanket
      ? `<span><i class="swatch" style="background:var(--blanket)"></i>Block all bots ${blanketN} · ${pct(blanketN, realTotal)}</span>`
      : `<span><i class="swatch" style="background:var(--blanket)"></i>Block all bots — next refresh</span>`;
    legend.innerHTML = `
      <span><i class="swatch" style="background:var(--block)"></i>Named GPTBot, blocked ${block} · ${pct(block, realTotal)}</span>
      ${blanketLabel}
      <span><i class="swatch" style="background:var(--allow)"></i>Named GPTBot, allowed ${allow} · ${pct(allow, realTotal)}</span>
      <span><i class="swatch" style="background:var(--partial)"></i>Named GPTBot, mixed ${partial} · ${pct(partial, realTotal)}</span>
    `;
  }
}

function groupKey(domain: string) {
  const host = domain.toLowerCase().replace(/\.$/, "");
  if (host === "amazon.com" || host.startsWith("amazon.")) return "amazon.com";
  return host;
}

function rowsForDomain(
  domain: string,
  named: LabRow[],
  blanket: LabRow[],
): LabRow[] {
  return [...named, ...blanket].filter((row) => row.domain === domain);
}

function paintDomainRows(body: Element, rows: LabRow[]) {
  if (rows.length === 0) {
    body.innerHTML = `<tr><td colspan="5" class="empty-cell">No named bot rule for this website in the current panel.</td></tr>`;
    return;
  }
  body.innerHTML = rows
    .map((row) => {
      const said =
        row.kind === "blanket" || row.purpose === "blanket"
          ? "Block all bots"
          : STATE_LABELS[row.state || ""] || row.state || "—";
      return `<tr>
        <td>${esc(row.token || row.agent || "GPTBot")}</td>
        <td>${esc(row.operator || "—")}</td>
        <td>${esc(purpose(row.purpose))}</td>
        <td>${esc(said)}</td>
        <td>${esc(row.valid_from || "")}</td>
      </tr>`;
    })
    .join("");
}

function loadLookupRows(
  agents: LabAgent[],
  domain: string,
): Promise<{ named: LabRow[]; blanket: LabRow[] }> {
  return fetch(LOOKUP_URL, { cache: "no-store" })
    .then((res) => {
      if (!res.ok) throw new Error(String(res.status));
      return res.json() as Promise<{ named?: [string, string, string][]; blanket?: [string, string][] }>;
    })
    .then((pack) => {
      const meta: Record<string, LabAgent> = {};
      for (const a of agents) meta[a.slug] = a;
      const named: LabRow[] = [];
      for (const [host, slug, state] of pack.named || []) {
        if (host !== domain) continue;
        const m = meta[slug];
        named.push({
          domain: host,
          agent_slug: slug,
          state,
          kind: "named",
          token: m?.token || slug,
          agent: m?.agent || slug,
          operator: m?.operator || "—",
          purpose: m?.purpose,
          group_key: groupKey(host),
        });
      }
      const blanket: LabRow[] = [];
      for (const [host, state] of pack.blanket || []) {
        if (host !== domain) continue;
        blanket.push({
          domain: host,
          state,
          kind: "blanket",
          agent_slug: "wildcard-star",
          token: "All bots (*)",
          agent: "All bots",
          operator: "Site-wide rule",
          purpose: "blanket",
          group_key: groupKey(host),
        });
      }
      return { named, blanket };
    });
}

function applyDomainPage(lab: LabSnapshot) {
  const host = document.querySelector<HTMLElement>("[data-domain-page]");
  if (!host) return;
  const fromAttr = host.getAttribute("data-domain-page") || "";
  const match = location.pathname.match(/\/domain\/([^/]+)/);
  const domain = fromAttr || (match ? decodeURIComponent(match[1]) : "");
  const heading = document.querySelector("[data-domain-heading]");
  const body = host.querySelector("[data-domain-rows]");
  if (!domain) {
    if (heading) heading.textContent = "Pick a website";
    if (body) {
      body.innerHTML = `<tr><td colspan="5" class="empty-cell">Open a website from Explore.</td></tr>`;
    }
    return;
  }
  if (heading) heading.textContent = domain;
  if (!body) return;
  const named = lab.named || [];
  const blanket = lab.blanket || [];
  const rows = rowsForDomain(domain, named, blanket);
  if (rows.length > 0) {
    paintDomainRows(body, rows);
    return;
  }
  body.innerHTML = `<tr><td colspan="5" class="empty-cell">Looking up…</td></tr>`;
  loadLookupRows(lab.by_agent || [], domain)
    .then((pack) => paintDomainRows(body, [...pack.named, ...pack.blanket]))
    .catch(() => paintDomainRows(body, []));
}

export function bootLiveLab(url: string) {
  fetch(url, { cache: "no-store" })
    .then((res) => {
      if (!res.ok) throw new Error(String(res.status));
      return res.json() as Promise<LabSnapshot>;
    })
    .then((lab) => {
      window.__CPI_LAB = lab;
      applySummary(lab);
      applyDomainPage(lab);
      window.dispatchEvent(new CustomEvent("cpi-lab", { detail: lab }));
    })
    .catch(() => {
      const host = document.querySelector("[data-domain-page]");
      const prerendered = Boolean(host?.getAttribute("data-domain-page"));
      if (prerendered) return;
      applyDomainPage({ generated_at: "", summary: {}, named: [], blanket: [] });
    });
}
