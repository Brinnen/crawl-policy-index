export function isSubscribed(
  user: { publicMetadata?: Record<string, unknown> } | null | undefined,
): boolean {
  return user?.publicMetadata?.subscribed === true;
}

export const PRICE_LABEL =
  (typeof import.meta.env.PUBLIC_PRICE_LABEL === "string" && import.meta.env.PUBLIC_PRICE_LABEL) ||
  "$49 / month";
