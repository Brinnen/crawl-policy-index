import type { APIRoute } from "astro";
import Stripe from "stripe";
import { clerkClient } from "@clerk/astro/server";
import { CLERK_ENABLED, userIdFromLocals } from "../../lib/clerk";
import { PRICE_HISTORY, PRICE_TABLE } from "../../lib/access";

export const prerender = false;

function originFrom(request: Request): string {
  const url = new URL(request.url);
  const proto = request.headers.get("x-forwarded-proto") || url.protocol.replace(":", "");
  const host = request.headers.get("x-forwarded-host") || request.headers.get("host") || url.host;
  return `${proto}://${host}`;
}

function planFromRequest(url: URL): "table" | "history" {
  return url.searchParams.get("plan") === "history" ? "history" : "table";
}

export const GET: APIRoute = async ({ locals, request }) => {
  const url = new URL(request.url);
  const plan = planFromRequest(url);
  const userId = userIdFromLocals(locals);
  if (!CLERK_ENABLED || !userId) {
    return new Response(null, {
      status: 302,
      headers: { Location: `/sign-up?redirect_url=${encodeURIComponent(`/api/checkout?plan=${plan}`)}` },
    });
  }

  const secret = import.meta.env.STRIPE_SECRET_KEY;
  const price =
    plan === "history"
      ? import.meta.env.STRIPE_PRICE_ID_HISTORY || PRICE_HISTORY
      : import.meta.env.STRIPE_PRICE_ID || PRICE_TABLE;
  if (!secret || !price) {
    return new Response("Stripe is not configured.", { status: 500 });
  }

  const user = await clerkClient(locals).users.getUser(userId);
  const email = user.primaryEmailAddress?.emailAddress;
  const existingCustomer = user.publicMetadata?.stripeCustomerId;
  const stripe = new Stripe(secret);
  const origin = originFrom(request);
  const session = await stripe.checkout.sessions.create({
    mode: "subscription",
    line_items: [{ price, quantity: 1 }],
    success_url: `${origin}/api/checkout-success?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${origin}/pricing`,
    client_reference_id: userId,
    customer: typeof existingCustomer === "string" ? existingCustomer : undefined,
    customer_email: existingCustomer || !email ? undefined : email,
    metadata: { userId, plan },
    subscription_data: { metadata: { userId, plan } },
    allow_promotion_codes: true,
  });

  if (!session.url) {
    return new Response("Stripe did not return a checkout URL.", { status: 502 });
  }
  return new Response(null, { status: 302, headers: { Location: session.url } });
};
