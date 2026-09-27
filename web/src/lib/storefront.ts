"use client";

import { useQuery } from "@tanstack/react-query";

import { getStorefrontConfigOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import type { StorefrontConfig } from "@/lib/api/generated/types.gen";

/** Shop facts (company, delivery, returns, warranty, FAQ) from config/storefront.yaml. */
export function useStorefront() {
  return useQuery({ ...getStorefrontConfigOptions(), staleTime: Infinity });
}

export type ShippingMethod = "standard" | "express";

export function addBusinessDays(start: Date, days: number): Date {
  const date = new Date(start);
  let added = 0;
  while (added < days) {
    date.setDate(date.getDate() + 1);
    const day = date.getDay();
    if (day !== 0 && day !== 6) added += 1;
  }
  return date;
}

export function shippingDays(config: StorefrontConfig, method: ShippingMethod): number {
  return method === "express" ? config.shipping.express_days : config.shipping.standard_days;
}

/** Latest arrival date for an order placed on `from` (weekends skipped, like checkout). */
export function deliveryBy(
  config: StorefrontConfig,
  method: ShippingMethod,
  from: Date = new Date(),
): Date {
  return addBusinessDays(from, shippingDays(config, method));
}

export function formatDay(date: Date): string {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(date);
}

/** Open the site-wide mini-cart or support chat from anywhere. */
export const openCart = () => window.dispatchEvent(new Event("volthaven:open-cart"));
export const openChat = (orderRef?: string) =>
  window.dispatchEvent(new CustomEvent("volthaven:open-chat", { detail: { orderRef } }));
