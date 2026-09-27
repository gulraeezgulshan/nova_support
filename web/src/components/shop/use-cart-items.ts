"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { useCart } from "@/components/shop/cart-context";
import { listProductsOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ProductOut } from "@/lib/api/generated/types.gen";

export type CartItem = { product: ProductOut; quantity: number };

/** Cart lines joined with current catalogue data (prices shown here; the server re-prices). */
export function useCartItems() {
  const cart = useCart();
  const products = useQuery(listProductsOptions());
  const bySku = new Map((products.data ?? []).map((p) => [p.sku, p]));
  const items: CartItem[] = cart.lines.flatMap((l) => {
    const product = bySku.get(l.sku);
    return product ? [{ product, quantity: l.quantity }] : [];
  });
  const subtotal = items.reduce((sum, i) => sum + i.product.price * i.quantity, 0);

  // Drop lines for products no longer sold (hidden or removed), so the badge, the cart
  // and checkout agree and a stale line cannot block checkout.
  const stale = products.isSuccess ? cart.lines.filter((l) => !bySku.has(l.sku)) : [];
  const staleKey = stale.map((l) => l.sku).join(",");
  useEffect(() => {
    if (staleKey) cart.removeMany(staleKey.split(","));
  }, [staleKey, cart]);

  return { cart, items, subtotal, loading: products.isPending };
}
