import type { APIRoute } from "astro";
import { createClerkClient } from "@clerk/astro/server";
import Stripe from "stripe";

export const POST: APIRoute = async ({ request }) => {
  const secret = import.meta.env.STRIPE_SECRET_KEY;
  const webhookSecret = import.meta.env.STRIPE_WEBHOOK_SECRET;
  const clerkSecret = import.meta.env.CLERK_SECRET_KEY;
  if (!secret || !webhookSecret || !clerkSecret) {
    return new Response("not configured", { status: 503 });
  }

  const stripe = new Stripe(secret);
  const raw = await request.text();
  const sig = request.headers.get("stripe-signature");
  if (!sig) return new Response("missing signature", { status: 400 });

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(raw, sig, webhookSecret);
  } catch {
    return new Response("invalid signature", { status: 400 });
  }

  const clerk = createClerkClient({ secretKey: clerkSecret });

  if (event.type === "checkout.session.completed") {
    const session = event.data.object as Stripe.Checkout.Session;
    const userId = session.client_reference_id || session.metadata?.userId;
    if (userId) {
      await clerk.users.updateUserMetadata(userId, {
        publicMetadata: {
          subscribed: true,
          stripeCustomerId: typeof session.customer === "string" ? session.customer : undefined,
        },
      });
    }
  }

  if (event.type === "customer.subscription.deleted") {
    const sub = event.data.object as Stripe.Subscription;
    const userId = sub.metadata?.userId;
    if (userId) {
      await clerk.users.updateUserMetadata(userId, {
        publicMetadata: { subscribed: false },
      });
    }
  }

  return new Response(JSON.stringify({ received: true }), {
    headers: { "content-type": "application/json" },
  });
};
