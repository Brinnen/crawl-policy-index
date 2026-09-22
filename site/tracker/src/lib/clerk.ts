export const CLERK_ENABLED = Boolean(
  import.meta.env.PUBLIC_CLERK_PUBLISHABLE_KEY && import.meta.env.CLERK_SECRET_KEY,
);

export function userIdFromLocals(locals: {
  auth?: () => { userId?: string | null };
}): string | null {
  try {
    return locals.auth?.()?.userId ?? null;
  } catch {
    return null;
  }
}
