import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const url = process.env.CPI_SNAPSHOT_URL || "http://178.128.255.20/snapshot/lab.json";
const out = fileURLToPath(new URL("../src/data/lab.json", import.meta.url));

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
