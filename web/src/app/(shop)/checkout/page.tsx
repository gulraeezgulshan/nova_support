"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Truck, Zap } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { EASE_OUT, Reveal } from "@/components/motion/reveal";
import { OrderSummary } from "@/components/shop/order-summary";
import { ProductImage } from "@/components/shop/product-image";
import { useCartItems } from "@/components/shop/use-cart-items";
import { Button } from "@/components/ui/button";
import {
  myShopOrdersQueryKey,
  placeOrderMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ShopOrderOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { useCurrency } from "@/lib/currency";
import { formatDate } from "@/lib/format";
import {
  deliveryBy,
  formatDay,
  type ShippingMethod,
  shippingDays,
  useStorefront,
} from "@/lib/storefront";
import { cn } from "@/lib/utils";

const SHIPPING: { value: ShippingMethod; label: string; icon: typeof Truck }[] = [
  { value: "standard", label: "Standard delivery", icon: Truck },
  { value: "express", label: "Express delivery", icon: Zap },
];

export default function CheckoutPage() {
  const queryClient = useQueryClient();
  const config = useStorefront().data;
  const { cart, items, subtotal } = useCartItems();
  const [shipping, setShipping] = useState<ShippingMethod>("standard");
  const currency = useCurrency();
  const [placed, setPlaced] = useState<ShopOrderOut[] | null>(null);
  const place = useMutation({
    ...placeOrderMutation(),
    onSuccess: (orders) => {
      setPlaced(orders);
      cart.clear();
      queryClient.invalidateQueries({ queryKey: myShopOrdersQueryKey() });
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  if (placed) return <Confirmation orders={placed} />;

  if (!items.length)
    return (
      <div className="mx-auto max-w-md space-y-4 px-4 py-24 text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Nothing to check out</h1>
        <Button asChild className="rounded-full">
          <Link href="/shop">Browse the shop</Link>
        </Button>
      </div>
    );

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <Reveal>
        <h1 className="mb-8 text-4xl font-semibold tracking-tight">Checkout</h1>
      </Reveal>
      <div className="grid gap-10 lg:grid-cols-[1fr_24rem]">
        <div className="space-y-10">
          <fieldset className="space-y-4">
            <legend className="mb-4 text-lg font-semibold">1. Delivery</legend>
            <div className="grid gap-3 sm:grid-cols-2">
              {SHIPPING.map(({ value, label, icon: Icon }) => {
                const selected = shipping === value;
                return (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setShipping(value)}
                    className={cn(
                      "relative rounded-2xl border p-5 text-left transition-all",
                      selected
                        ? "border-brand bg-brand-soft ring-1 ring-brand"
                        : "hover:border-foreground/30",
                    )}
                  >
                    {selected ? (
                      <motion.span
                        layoutId="shipping-check"
                        className="absolute top-4 right-4 flex size-5 items-center justify-center rounded-full bg-brand text-brand-foreground"
                      >
                        <Check className="size-3" />
                      </motion.span>
                    ) : null}
                    <Icon className="size-5 text-brand" />
                    <p className="mt-3 font-medium">{label}</p>
                    {config ? (
                      <>
                        <p className="text-sm text-muted-foreground">
                          Within {shippingDays(config, value)} business day
                          {shippingDays(config, value) === 1 ? "" : "s"}
                        </p>
                        <p className="mt-2 text-sm">
                          Arrives by <strong>{formatDay(deliveryBy(config, value))}</strong>
                        </p>
                      </>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </fieldset>
          <section className="space-y-4">
            <h2 className="text-lg font-semibold">2. Review your items</h2>
            <ul className="divide-y rounded-2xl border">
              {items.map(({ product, quantity }) => (
                <li key={product.sku} className="flex items-center gap-4 p-4">
                  <ProductImage
                    url={product.images[0]?.url}
                    line={product.product_line}
                    alt={product.name}
                    className="size-16 rounded-xl border"
                  />
                  <span className="flex-1 font-medium">{product.name}</span>
                  <span className="text-sm text-muted-foreground">Qty {quantity}</span>
                </li>
              ))}
            </ul>
            <Button asChild variant="link" className="px-0">
              <Link href="/cart">Edit cart</Link>
            </Button>
          </section>
        </div>
        <OrderSummary items={items} subtotal={subtotal}>
          <Button
            size="lg"
            className="h-12 w-full rounded-full bg-brand text-brand-foreground hover:bg-brand/90"
            disabled={place.isPending}
            onClick={() =>
              place.mutate({
                body: {
                  lines: items.map((i) => ({ sku: i.product.sku, quantity: i.quantity })),
                  shipping_method: shipping,
                  currency: currency.code as "USD" | "PKR" | "EUR" | "GBP" | "AED",
                },
              })
            }
          >
            {place.isPending ? "Placing order…" : "Place order"}
          </Button>
        </OrderSummary>
      </div>
    </div>
  );
}

function Confirmation({ orders }: { orders: ShopOrderOut[] }) {
  const first = orders[0];
  return (
    <div className="mx-auto max-w-xl px-4 py-20 text-center">
      <motion.div
        initial={{ scale: 0, rotate: -45 }}
        animate={{ scale: 1, rotate: 0 }}
        transition={{ type: "spring", stiffness: 260, damping: 18 }}
        className="mx-auto flex size-20 items-center justify-center rounded-full bg-brand text-brand-foreground shadow-xl shadow-brand/30"
      >
        <motion.svg viewBox="0 0 24 24" className="size-10" fill="none" aria-hidden>
          <motion.path
            d="M5 12.5l4.5 4.5L19 7.5"
            stroke="currentColor"
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.5, delay: 0.3, ease: EASE_OUT }}
          />
        </motion.svg>
      </motion.div>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.4, ease: EASE_OUT }}
        className="mt-8 space-y-3"
      >
        <h1 className="text-4xl font-semibold tracking-tight">Order placed</h1>
        <p className="text-muted-foreground">
          Thank you! Your purchase reference is{" "}
          <span className="font-mono font-medium text-foreground">
            {first?.checkout_ref ?? first?.order_ref}
          </span>
          .
        </p>
        {first ? (
          <p className="text-muted-foreground">
            {orders.length} item{orders.length === 1 ? "" : "s"}, due by{" "}
            <strong className="text-foreground">{formatDate(first.committed_delivery_date)}</strong>{" "}
            ({first.shipping_method} delivery).
          </p>
        ) : null}
        <div className="flex flex-wrap justify-center gap-3 pt-4">
          <Button asChild size="lg" className="rounded-full bg-brand text-brand-foreground">
            <Link href="/orders">View my orders</Link>
          </Button>
          <Button asChild size="lg" variant="outline" className="rounded-full">
            <Link href="/shop">Keep shopping</Link>
          </Button>
        </div>
      </motion.div>
    </div>
  );
}
