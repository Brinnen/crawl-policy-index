import { PURPOSE_LABELS, STATE_LABELS } from "../lib/labels";

export const SNAPSHOT_URL = "https://crawlpolicyindex.org/snapshot/lab.json";

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
  const rows = [...named, ...blanket].filter((row) => row.domain === domain);
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
