// Singleton Stripe SDK (только сервер). apiVersion не пинуем — используем дефолт SDK.

import Stripe from "stripe";
import { stripeSecretKey } from "./config";

let cached: Stripe | null = null;

export const stripe = (): Stripe => {
  if (cached == null) {
    cached = new Stripe(stripeSecretKey());
  }
  return cached;
};
