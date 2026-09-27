"use client";

import type { CartItem } from "@/components/shop/use-cart-items";
import { formatMoney } from "@/lib/format";

/** Line totals and the order total (prices are confirmed by the server at checkout). */
export function OrderSummary({
  items,
  subtotal,
  shippingNote,
  children,
}: {
  items?: CartItem[];
  subtotal: number;
  shippingNote?: string;
  children?: React.ReactNode;
}) {
  return (
    <aside className="h-fit space-y-4 rounded-3xl border bg-muted/30 p-6 lg:sticky lg:top-24">
      <h2 className="text-lg font-semibold">Order summary</h2>
      {items ? (
        <ul className="space-y-2 text-sm">
          {items.map(({ product, quantity }) => (
            <li key={product.sku} className="flex justify-between gap-4">
              <span className="text-muted-foreground">
                {product.name} × {quantity}
              </span>
              <span className="tabular-nums">{formatMoney(product.price * quantity)}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <dl className="space-y-2 border-t pt-4 text-sm">
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Subtotal</dt>
          <dd className="tabular-nums">{formatMoney(subtotal)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Shipping</dt>
          <dd>{shippingNote ?? "Free"}</dd>
        </div>
        <div className="flex justify-between border-t pt-3 text-base font-semibold">
          <dt>Total</dt>
          <dd className="tabular-nums">{formatMoney(subtotal)}</dd>
        </div>
      </dl>
      {children}
      <p className="text-center text-xs text-muted-foreground">
        Demo shop: no payment is taken and nothing is shipped.
      </p>
    </aside>
  );
}
