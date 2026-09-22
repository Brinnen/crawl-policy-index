import type { APIRoute } from "astro";
import Stripe from "stripe";
import { clerkClient } from "@clerk/astro/server";
import { CLERK_ENABLED, userIdFromLocals } from "../../lib/clerk";
import { planFromPriceId } from "../../lib/access";

export const prerender = false;

export const GET: APIRoute = async ({ locals, request }) => {
  const userId = userIdFromLocals(locals);
  const url = new URL(request.url);
  const sessionId = url.searchParams.get("session_id");
  if (!CLERK_ENABLED || !userId || !sessionId || !import.meta.env.STRIPE_SECRET_KEY) {
    return new Response(null, { status: 302, headers: { Location: "/app" } });
  }

  const stripe = new Stripe(import.meta.env.STRIPE_SECRET_KEY);
  const session = await stripe.checkout.sessions.retrieve(sessionId, {
    expand: ["line_items.data.price"],
  });
  if (session.client_reference_id !== userId || session.status !== "complete") {
    return new Response(null, { status: 302, headers: { Location: "/pricing" } });
  }

  const priceId = session.line_items?.data?.[0]?.price?.id;
  const plan =
    session.metadata?.plan === "history" || session.metadata?.plan === "table"
      ? session.metadata.plan
      : planFromPriceId(priceId);

  const customerId =
    typeof session.customer === "string" ? session.customer : session.customer?.id;
  await clerkClient(locals).users.updateUserMetadata(userId, {
    publicMetadata: {
      subscribed: true,
      plan,
      stripeCustomerId: customerId,
    },
  });
  return new Response(null, {
    status: 302,
    headers: { Location: plan === "history" ? "/history" : "/app" },
  });
};
