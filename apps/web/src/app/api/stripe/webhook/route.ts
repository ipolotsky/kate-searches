import type { NextRequest } from "next/server";
import type Stripe from "stripe";
import { stripe } from "@/lib/stripe/client";
import { isStripeConfigured, stripeWebhookSecret } from "@/lib/stripe/config";
import {
  tenantIdFromSubscription,
  tenantUpdateForSubscription,
} from "@/lib/stripe/provisioning";
import { createAdminClient } from "@/lib/supabase/admin";

export const dynamic = "force-dynamic";

type AdminClient = ReturnType<typeof createAdminClient>;

// Вебхук Stripe: единственная точка, где план/бюджет тенанта провижинятся из подписки. Landing на
// web (единственный внешне доступный сервис). Подпись проверяем по СЫРОМУ телу. Дедуп по event.id:
// claim-строка в stripe_events; при сбое хендлера строку удаляем, чтобы Stripe-ретрай переобработал.
export async function POST(request: NextRequest): Promise<Response> {
  if (!isStripeConfigured()) {
    return new Response("not configured", { status: 503 });
  }
  const signature = request.headers.get("stripe-signature");
  if (signature == null) {
    return new Response("no signature", { status: 400 });
  }

  const body = await request.text();
  let event: Stripe.Event;
  try {
    event = stripe().webhooks.constructEvent(body, signature, stripeWebhookSecret());
  } catch {
    return new Response("invalid signature", { status: 400 });
  }

  const admin = createAdminClient();
  const claim = await admin.from("stripe_events").insert({ event_id: event.id, type: event.type });
  if (claim.error != null) {
    // 23505 unique_violation => событие уже принято (дубликат доставки): не обрабатываем повторно.
    if (claim.error.code === "23505") {
      return new Response("duplicate", { status: 200 });
    }
    return new Response("db error", { status: 500 });
  }

  try {
    await handleEvent(event, admin);
  } catch {
    // Откатываем claim, чтобы Stripe-ретрай переобработал (иначе провижининг потерян навсегда).
    await admin.from("stripe_events").delete().eq("event_id", event.id);
    return new Response("handler error", { status: 500 });
  }
  return new Response("ok", { status: 200 });
}

const handleEvent = async (event: Stripe.Event, admin: AdminClient): Promise<void> => {
  if (event.type === "checkout.session.completed") {
    const session = event.data.object as Stripe.Checkout.Session;
    const tenantId = session.client_reference_id ?? session.metadata?.tenant_id ?? null;
    if (tenantId != null && typeof session.customer === "string") {
      await admin
        .from("tenants")
        .update({
          stripe_customer_id: session.customer,
          stripe_subscription_id:
            typeof session.subscription === "string" ? session.subscription : null,
        })
        .eq("id", tenantId);
    }
    return;
  }

  if (
    event.type === "customer.subscription.created" ||
    event.type === "customer.subscription.updated" ||
    event.type === "customer.subscription.deleted"
  ) {
    const subscription = event.data.object as Stripe.Subscription;
    const tenantId = tenantIdFromSubscription(subscription);
    const update = tenantUpdateForSubscription(subscription);
    if (tenantId != null) {
      await admin.from("tenants").update(update).eq("id", tenantId);
    } else if (typeof subscription.customer === "string") {
      await admin.from("tenants").update(update).eq("stripe_customer_id", subscription.customer);
    }
  }
};
