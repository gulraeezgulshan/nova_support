"use client";

import { useQuery } from "@tanstack/react-query";
import { LifeBuoy } from "lucide-react";
import Link from "next/link";

import { OrderTracker } from "@/components/shop/order-tracker";
import { ProductImage } from "@/components/shop/product-image";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { myShopOrdersOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ShopOrderOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { formatLocal } from "@/lib/currency";
import { formatDate } from "@/lib/format";

function businessDaysLate(due: string, delivered: string): number {
  let days = 0;
  const current = new Date(due);
  const end = new Date(delivered);
  while (current < end) {
    current.setDate(current.getDate() + 1);
    if (current.getDay() !== 0 && current.getDay() !== 6) days += 1;
  }
  return days;
}

function statusLine(o: ShopOrderOut): { text: string; tone: "default" | "late" | "bad" } {
  if (o.status === "lost") return { text: "Lost in transit", tone: "bad" };
  if (o.stage === "cancelled") return { text: "Cancelled", tone: "default" };
  if (o.stage === "returned") return { text: "Returned", tone: "default" };
  if (o.stage === "return_requested") return { text: "Return requested", tone: "default" };
  if (o.stage === "return_refused") return { text: "Return refused", tone: "bad" };
  if (o.delivered_date) {
    const late = businessDaysLate(o.committed_delivery_date, o.delivered_date);
    return late
      ? {
          text: `Delivered ${formatDate(o.delivered_date)}, ${late} business day${late === 1 ? "" : "s"} late`,
          tone: "late",
        }
      : { text: `Delivered ${formatDate(o.delivered_date)}`, tone: "default" };
  }
  if (o.expected_delivery_date)
    return { text: `Delayed, now expected ${formatDate(o.expected_delivery_date)}`, tone: "late" };
  const onItsWay = o.stage === "shipped" || o.stage === "out_for_delivery";
  return {
    text: `${onItsWay ? "On its way" : "Processing"}, due ${formatDate(o.committed_delivery_date)}`,
    tone: "default",
  };
}

export function OrderList({ onHelp }: { onHelp: (orderRef: string) => void }) {
  const orders = useQuery(myShopOrdersOptions());

  if (orders.isPending) return <Skeleton className="h-64 w-full" />;
  if (orders.isError)
    return <p className="text-sm text-destructive">{apiErrorMessage(orders.error)}</p>;
  if (!orders.data.length)
    return (
      <div className="space-y-3 rounded-3xl border border-dashed py-16 text-center">
        <p className="text-muted-foreground">You have no orders yet.</p>
        <Button asChild className="rounded-full bg-brand text-brand-foreground">
          <Link href="/shop">Start shopping</Link>
        </Button>
      </div>
    );

  const groups = new Map<string, ShopOrderOut[]>();
  for (const o of orders.data) {
    const key = o.checkout_ref ?? o.order_ref;
    groups.set(key, [...(groups.get(key) ?? []), o]);
  }

  return (
    <div className="space-y-4">
      {[...groups.entries()].map(([key, group]) => (
        <section key={key} className="overflow-hidden rounded-3xl border">
          <header className="flex flex-wrap items-center justify-between gap-2 border-b bg-muted/30 px-5 py-3 text-sm">
            <span className="font-medium">{key.startsWith("CHK-") ? `Purchase ${key}` : key}</span>
            <span className="text-muted-foreground">
              Ordered {formatDate(group[0].order_date)} · {group[0].shipping_method} shipping
            </span>
          </header>
          <ul className="divide-y">
            {group.map((o) => {
              const status = statusLine(o);
              return (
                <li key={o.order_ref} className="flex flex-wrap items-center gap-4 p-5">
                  <ProductImage
                    url={o.image_url}
                    line={o.product_category}
                    alt={o.product_name}
                    className="size-16 rounded-xl border"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">
                      {o.product_name} {o.quantity > 1 ? `× ${o.quantity}` : null}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {o.order_ref} · {formatLocal(o)}
                    </p>
                    <Badge
                      variant="outline"
                      className={
                        status.tone === "bad"
                          ? "mt-1 border-red-600/40 text-red-700 dark:text-red-400"
                          : status.tone === "late"
                            ? "mt-1 border-amber-600/40 text-amber-700 dark:text-amber-400"
                            : "mt-1"
                      }
                    >
                      {status.text}
                    </Badge>
                    <OrderTracker order={o} />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-full"
                      onClick={() => onHelp(o.order_ref)}
                    >
                      <LifeBuoy /> Get help
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
