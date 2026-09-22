import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const url = process.env.CPI_SNAPSHOT_URL || "http://178.128.255.20/snapshot/lab.json";
const out = fileURLToPath(new URL("../src/data/lab.json", import.meta.url));
const previewUrl = process.env.CPI_PREVIEW_URL || "http://178.128.255.20/snapshot/preview.json";
const previewOut = fileURLToPath(new URL("../src/data/preview.json", import.meta.url));

try {
  const res = await fetch(url, { signal: AbortSignal.timeout(20000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const text = await res.text();
  const parsed = JSON.parse(text);
  if (!parsed?.summary || parsed.summary.panel_size == null) {
    throw new Error("snapshot missing summary.panel_size");
  }
  writeFileSync(out, text.endsWith("\n") ? text : `${text}\n`);
  console.log(
    `pulled snapshot panel=${parsed.panel_version} size=${parsed.summary.panel_size}`,
  );
} catch (err) {
  const message = err instanceof Error ? err.message : String(err);
  console.warn(`snapshot pull skipped (${message}); using committed lab.json`);
}

try {
  const committed = JSON.parse(readFileSync(previewOut, "utf8"));
  const res = await fetch(previewUrl, { signal: AbortSignal.timeout(20000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const live = JSON.parse(await res.text());
  if (!Array.isArray(live?.named) && !Array.isArray(committed?.sites)) {
    throw new Error("preview missing sites");
  }
  const merged = {
    named: Array.isArray(live.named) && live.named.length ? live.named : committed.named || [],
    blanket: Array.isArray(live.blanket) && live.blanket.length ? live.blanket : committed.blanket || [],
    sites: committed.sites,
  };
  if (!Array.isArray(merged.sites) || !merged.sites.length) {
    throw new Error("committed preview missing sites");
  }
  writeFileSync(previewOut, `${JSON.stringify(merged)}\n`);
  console.log(`pulled preview named=${merged.named.length} kept sites=${merged.sites.length}`);
} catch (err) {
  const message = err instanceof Error ? err.message : String(err);
  console.warn(`preview pull skipped (${message}); using committed preview.json`);
}
