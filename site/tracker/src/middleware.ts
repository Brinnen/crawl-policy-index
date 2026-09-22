import { clerkMiddleware } from "@clerk/astro/server";
import type { MiddlewareHandler } from "astro";
import { CLERK_ENABLED } from "./lib/clerk";

export const onRequest: MiddlewareHandler = CLERK_ENABLED
  ? clerkMiddleware()
  : async (_context, next) => next();
