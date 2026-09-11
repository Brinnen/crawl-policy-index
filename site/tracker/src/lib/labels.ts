export const PURPOSE_LABELS: Record<string, string> = {
  training: "Training AI",
  search_index: "AI search",
  user_fetch: "When a person asks",
  opt_out_token: "Opt-out signal",
  agentic: "Autonomous agent",
  unknown: "Unclear",
  blanket: "Block all bots",
};

export const STATE_LABELS: Record<string, string> = {
  BLOCKED: "Blocked",
  ALLOWED: "Allowed",
  PARTIAL: "Mixed",
};

export const BLANKET_SLUG = "wildcard-star";
export const BLANKET_TOKEN = "All bots (*)";

export function purposeLabel(value: string | undefined | null): string {
  if (!value) return "—";
  return PURPOSE_LABELS[value] ?? value.replaceAll("_", " ");
}
