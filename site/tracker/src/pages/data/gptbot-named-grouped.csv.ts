import lab from "../../data/lab.json";

export const prerender = true;

function csvEscape(value: string | number): string {
  const s = String(value);
  if (/[",\n]/.test(s)) return `"${s.replaceAll('"', '""')}"`;
  return s;
}

export function GET() {
  const header = [
    "group_key",
    "domain_rows",
    "named_block_rows",
    "named_allow_rows",
    "named_partial_rows",
  ];
  const lines = [header.join(",")];
  for (const row of lab.grouped) {
    lines.push(
      [
        row.group_key,
        row.domain_rows,
        row.named_block_rows,
        row.named_allow_rows,
        row.named_partial_rows,
      ]
        .map(csvEscape)
        .join(","),
    );
  }
  return new Response(lines.join("\n") + "\n", {
    headers: { "Content-Type": "text/csv; charset=utf-8" },
  });
}
