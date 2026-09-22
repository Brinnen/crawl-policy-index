export type Plan = "table" | "history" | "";

export function isSubscribed(
  user: { publicMetadata?: Record<string, unknown> } | null | undefined,
): boolean {
  return user?.publicMetadata?.subscribed === true;
}

export function planOf(
  user: { publicMetadata?: Record<string, unknown> } | null | undefined,
): Plan {
  const plan = user?.publicMetadata?.plan;
  if (plan === "history" || plan === "table") return plan;
  return isSubscribed(user) ? "table" : "";
}

export function isHistory(
  user: { publicMetadata?: Record<string, unknown> } | null | undefined,
): boolean {
  return planOf(user) === "history";
}

export const PRICE_TABLE = "price_1UIP4wCuAgBI9dTCek0CwS0k";
export const PRICE_HISTORY = "price_1UIQynCuAgBI9dTCSVWeCcXP";

export const PRICE_LABEL =
  (typeof import.meta.env.PUBLIC_PRICE_LABEL === "string" && import.meta.env.PUBLIC_PRICE_LABEL) ||
  "$49 / month";

export const HISTORY_PRICE_LABEL =
  (typeof import.meta.env.PUBLIC_HISTORY_PRICE_LABEL === "string" &&
    import.meta.env.PUBLIC_HISTORY_PRICE_LABEL) ||
  "$199 / month";

export function planFromPriceId(priceId: string | undefined | null): Plan {
  if (!priceId) return "table";
  if (priceId === PRICE_HISTORY || priceId === import.meta.env.STRIPE_PRICE_ID_HISTORY) {
    return "history";
  }
  return "table";
}
