import lab from "../../data/lab.json";

export const prerender = true;

function csvEscape(value: string | number): string {
  const s = String(value);
  if (/[",\n]/.test(s)) return `"${s.replaceAll('"', '""')}"`;
  return s;
}

export function GET() {
  const header = ["domain", "state", "group_key", "valid_from"];
  const lines = [header.join(",")];
  for (const row of lab.named) {
    lines.push(
      [row.domain, row.state, row.group_key, row.valid_from].map(csvEscape).join(","),
    );
  }
  return new Response(lines.join("\n") + "\n", {
    headers: { "Content-Type": "text/csv; charset=utf-8" },
  });
}
