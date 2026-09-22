import type { APIRoute } from "astro";
import Stripe from "stripe";
import { clerkClient } from "@clerk/astro/server";
import { CLERK_ENABLED } from "../../lib/clerk";
import { planFromPriceId, type Plan } from "../../lib/access";

export const prerender = false;

function clerkFromLocals(locals: App.Locals) {
  return clerkClient(locals);
}

function planFromSubscription(sub: Stripe.Subscription): Plan {
  const fromMeta = sub.metadata?.plan;
  if (fromMeta === "history" || fromMeta === "table") return fromMeta;
  const priceId = sub.items.data[0]?.price?.id;
  return planFromPriceId(priceId);
}

async function mark(
  locals: App.Locals,
  userId: string,
  customerId: string | null,
  subscribed: boolean,
  plan: Plan,
) {
  await clerkFromLocals(locals).users.updateUserMetadata(userId, {
    publicMetadata: {
      subscribed,
      plan: subscribed ? plan : "",
      stripeCustomerId: customerId,
    },
  });
}

export const POST: APIRoute = async ({ locals, request }) => {
  const secret = import.meta.env.STRIPE_SECRET_KEY;
  const webhookSecret = import.meta.env.STRIPE_WEBHOOK_SECRET;
  if (!CLERK_ENABLED || !secret || !webhookSecret) {
    return new Response("Stripe webhook is not configured.", { status: 500 });
  }

  const stripe = new Stripe(secret);
  const signature = request.headers.get("stripe-signature");
  if (!signature) return new Response("Missing signature.", { status: 400 });

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(await request.text(), signature, webhookSecret);
  } catch {
    return new Response("Bad signature.", { status: 400 });
  }

  if (event.type === "checkout.session.completed") {
    const session = event.data.object as Stripe.Checkout.Session;
    const userId = session.client_reference_id || session.metadata?.userId;
    const customerId = typeof session.customer === "string" ? session.customer : session.customer?.id;
    if (userId && customerId) {
      let plan: Plan =
        session.metadata?.plan === "history" || session.metadata?.plan === "table"
          ? session.metadata.plan
          : "table";
      if (typeof session.subscription === "string") {
        const sub = await stripe.subscriptions.retrieve(session.subscription);
        plan = planFromSubscription(sub);
      }
      await mark(locals, userId, customerId, true, plan);
    }
  }

  if (event.type === "customer.subscription.updated") {
    const sub = event.data.object as Stripe.Subscription;
    const userId = sub.metadata?.userId;
    const customerId = typeof sub.customer === "string" ? sub.customer : sub.customer.id;
    const live = sub.status === "active" || sub.status === "trialing";
    if (userId) {
      await mark(locals, userId, customerId, live, planFromSubscription(sub));
    }
  }

  if (event.type === "customer.subscription.deleted") {
    const sub = event.data.object as Stripe.Subscription;
    const userId = sub.metadata?.userId;
    const customerId = typeof sub.customer === "string" ? sub.customer : sub.customer.id;
    if (userId) {
      await mark(locals, userId, customerId, false, "");
    }
  }

  return new Response(JSON.stringify({ received: true }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
};
