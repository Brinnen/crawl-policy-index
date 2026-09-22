import type { APIRoute } from "astro";
import Stripe from "stripe";

export const GET: APIRoute = async ({ locals, redirect, url }) => {
  const { userId } = locals.auth();
  if (!userId) return redirect("/sign-in");

  const secret = import.meta.env.STRIPE_SECRET_KEY;
  const price = import.meta.env.STRIPE_PRICE_ID;
  if (!secret || !price) {
    return new Response("Stripe is not configured yet. Add STRIPE_SECRET_KEY and STRIPE_PRICE_ID.", {
      status: 503,
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }

  const stripe = new Stripe(secret);
  const origin = url.origin;
  const session = await stripe.checkout.sessions.create({
    mode: "subscription",
    line_items: [{ price, quantity: 1 }],
    success_url: `${origin}/api/checkout-success?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${origin}/pricing`,
    client_reference_id: userId,
    metadata: { userId },
    subscription_data: { metadata: { userId } },
    allow_promotion_codes: true,
  });
  if (!session.url) {
    return new Response("Could not start checkout.", { status: 500 });
  }
  return redirect(session.url);
};
