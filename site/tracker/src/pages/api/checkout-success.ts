import type { APIRoute } from "astro";
import { clerkClient } from "@clerk/astro/server";
import Stripe from "stripe";

export const GET: APIRoute = async (context) => {
  const { locals, redirect, url } = context;
  let userId: string | null = null;
  try {
    userId = locals.auth?.()?.userId ?? null;
  } catch {
    userId = null;
  }
  if (!userId) return redirect("/sign-in");

  const secret = import.meta.env.STRIPE_SECRET_KEY;
  const sessionId = url.searchParams.get("session_id");
  if (!secret || !sessionId) return redirect("/pricing");

  const stripe = new Stripe(secret);
  const session = await stripe.checkout.sessions.retrieve(sessionId);
  if (session.client_reference_id !== userId) return redirect("/pricing");
  if (session.status !== "complete" && session.payment_status === "unpaid") {
    return redirect("/pricing");
  }

  const client = clerkClient(context);
  await client.users.updateUserMetadata(userId, {
    publicMetadata: {
      subscribed: true,
      stripeCustomerId: typeof session.customer === "string" ? session.customer : undefined,
    },
  });
  return redirect("/app");
};
