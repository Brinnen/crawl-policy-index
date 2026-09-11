import lab from "../../data/lab.json";

export const prerender = true;

export function GET() {
  return new Response(JSON.stringify(lab, null, 2) + "\n", {
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
