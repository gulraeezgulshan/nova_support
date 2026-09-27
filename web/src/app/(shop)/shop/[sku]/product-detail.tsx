"use client";

import { useQuery } from "@tanstack/react-query";
import { Check, ChevronRight, Minus, Plus, RotateCcw, ShieldCheck, Truck } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { EASE_OUT, Reveal } from "@/components/motion/reveal";
import { MAX_QUANTITY, useCart } from "@/components/shop/cart-context";
import { flyToCart } from "@/components/shop/fly-to-cart";
import { PRODUCT_LINES } from "@/components/shop/lines";
import { ProductImage } from "@/components/shop/product-image";
import { ProductRail } from "@/components/shop/product-carousel";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  getProductOptions,
  listProductsOptions,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ProductOut } from "@/lib/api/generated/types.gen";
import { formatMoney } from "@/lib/format";
import { deliveryBy, formatDay, openCart, useStorefront } from "@/lib/storefront";
import { cn } from "@/lib/utils";

export function ProductDetail({ sku }: { sku: string }) {
  const product = useQuery(getProductOptions({ path: { sku } }));
  if (product.isPending)
    return (
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-10 md:grid-cols-2">
        <Skeleton className="aspect-square rounded-3xl" />
        <div className="space-y-4">
          <Skeleton className="h-10 w-2/3" />
          <Skeleton className="h-8 w-1/4" />
          <Skeleton className="h-32" />
        </div>
      </div>
    );
  if (product.isError)
    return (
      <div className="mx-auto max-w-xl px-4 py-24 text-center">
        <h1 className="text-2xl font-semibold">This product is not available</h1>
        <p className="mt-2 text-muted-foreground">It may have been removed from the range.</p>
        <Button asChild className="mt-6 rounded-full">
          <Link href="/shop">Back to the shop</Link>
        </Button>
      </div>
    );
  return <Detail product={product.data} />;
}

function Detail({ product: p }: { product: ProductOut }) {
  const cart = useCart();
  const config = useStorefront().data;
  const [quantity, setQuantity] = useState(1);
  const line = PRODUCT_LINES.find((l) => l.code === p.product_line);

  return (
    <div className="mx-auto max-w-7xl space-y-20 px-4 py-8">
      <div>
        <nav
          aria-label="Breadcrumb"
          className="mb-6 flex items-center gap-1 text-sm text-muted-foreground"
        >
          <Link href="/shop" className="hover:text-foreground">
            Shop
          </Link>
          <ChevronRight className="size-3.5" />
          <Link href={`/shop?line=${p.product_line}`} className="hover:text-foreground">
            {line?.label ?? p.product_line}
          </Link>
          <ChevronRight className="size-3.5" />
          <span className="line-clamp-1 text-foreground">{p.name}</span>
        </nav>
        <div className="grid gap-10 md:grid-cols-2 lg:gap-16">
          <Gallery product={p} />
          <Reveal className="space-y-6">
            <div className="space-y-2">
              <p className="text-sm font-medium tracking-wide text-brand uppercase">
                {line?.label}
              </p>
              <h1 className="text-4xl font-semibold tracking-tight">{p.name}</h1>
              <p className="text-3xl font-semibold tabular-nums">{formatMoney(p.price)}</p>
            </div>
            <p className="text-lg text-muted-foreground">{p.description}</p>
            <ul className="grid gap-2 sm:grid-cols-2">
              {p.specs.map((s) => (
                <li key={s} className="flex items-center gap-2 text-sm">
                  <Check className="size-4 shrink-0 text-brand" /> {s}
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center rounded-full border">
                <Button
                  variant="ghost"
                  size="icon"
                  className="rounded-full"
                  aria-label="One fewer"
                  disabled={quantity <= 1}
                  onClick={() => setQuantity((q) => q - 1)}
                >
                  <Minus />
                </Button>
                <span className="w-8 text-center tabular-nums" aria-live="polite">
                  {quantity}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="rounded-full"
                  aria-label="One more"
                  disabled={quantity >= MAX_QUANTITY}
                  onClick={() => setQuantity((q) => q + 1)}
                >
                  <Plus />
                </Button>
              </div>
              <Button
                size="lg"
                className="h-12 flex-1 rounded-full bg-brand text-brand-foreground shadow-lg shadow-brand/20 hover:bg-brand/90 sm:flex-none sm:px-10"
                onClick={(event) => {
                  flyToCart(event.currentTarget);
                  cart.add(p.sku, quantity);
                  toast.success(`${quantity} × ${p.name} added to your cart`, {
                    action: { label: "View cart", onClick: openCart },
                  });
                }}
              >
                Add to cart
              </Button>
            </div>
            {config ? (
              <div className="space-y-3 rounded-2xl border bg-muted/30 p-4 text-sm">
                <p className="flex items-start gap-3">
                  <Truck className="mt-0.5 size-4 shrink-0 text-brand" />
                  <span>
                    Order today, arrives by{" "}
                    <strong>{formatDay(deliveryBy(config, "standard"))}</strong> with standard
                    delivery, or <strong>{formatDay(deliveryBy(config, "express"))}</strong> with
                    express.
                  </span>
                </p>
                <p className="flex items-start gap-3">
                  <RotateCcw className="mt-0.5 size-4 shrink-0 text-brand" />
                  {config.returns.window_days}-day returns on unused items.
                </p>
                <p className="flex items-start gap-3">
                  <ShieldCheck className="mt-0.5 size-4 shrink-0 text-brand" />
                  {config.warranty.months}-month limited warranty ({config.warranty.extended_months}{" "}
                  months with VoltCare+).
                </p>
              </div>
            ) : null}
          </Reveal>
        </div>
      </div>
      <Reveal>
        <Tabs defaultValue="details" className="gap-6">
          <TabsList>
            <TabsTrigger value="details">Details</TabsTrigger>
            <TabsTrigger value="shipping">Shipping</TabsTrigger>
            <TabsTrigger value="returns">Returns &amp; warranty</TabsTrigger>
          </TabsList>
          <TabsContent value="details" className="max-w-3xl space-y-4">
            <p>{p.description}</p>
            <dl className="divide-y rounded-2xl border">
              {p.specs.map((s, i) => (
                <div key={s} className="flex gap-4 px-4 py-3 text-sm">
                  <dt className="w-32 shrink-0 text-muted-foreground">Feature {i + 1}</dt>
                  <dd>{s}</dd>
                </div>
              ))}
              <div className="flex gap-4 px-4 py-3 text-sm">
                <dt className="w-32 shrink-0 text-muted-foreground">Product code</dt>
                <dd className="font-mono">{p.sku}</dd>
              </div>
            </dl>
          </TabsContent>
          <TabsContent value="shipping" className="max-w-3xl space-y-3 text-muted-foreground">
            {config ? (
              <>
                <p>
                  Standard delivery arrives within {config.shipping.standard_days} business days of
                  dispatch; express within {config.shipping.express_days}. Weekends don&apos;t
                  count.
                </p>
                <p>
                  If a standard order arrives more than {config.shipping.late_threshold_days}{" "}
                  business days late you can receive store credit of{" "}
                  {config.shipping.late_credit_pct}% of the order value (up to USD{" "}
                  {config.shipping.late_credit_cap_usd}). Late express orders get the express fee
                  back.
                </p>
                <Link href="/shipping" className="text-brand hover:underline">
                  Read the full delivery policy
                </Link>
              </>
            ) : null}
          </TabsContent>
          <TabsContent value="returns" className="max-w-3xl space-y-3 text-muted-foreground">
            {config ? (
              <>
                <p>
                  Unused items in their original packaging can be returned within{" "}
                  {config.returns.window_days} days of delivery. Refunds reach your original payment
                  method within {config.returns.refund_min_days} to {config.returns.refund_max_days}{" "}
                  business days of us receiving the item.
                </p>
                <p>
                  Every product carries a {config.warranty.months}-month limited warranty from the
                  delivery date.
                </p>
                <div className="flex gap-4">
                  <Link href="/returns" className="text-brand hover:underline">
                    Returns policy
                  </Link>
                  <Link href="/warranty" className="text-brand hover:underline">
                    Warranty
                  </Link>
                </div>
              </>
            ) : null}
          </TabsContent>
        </Tabs>
      </Reveal>
      <Related product={p} />
    </div>
  );
}

function Gallery({ product: p }: { product: ProductOut }) {
  const [selected, setSelected] = useState(0);
  const [zoom, setZoom] = useState<{ x: number; y: number } | null>(null);
  const image = p.images[selected] ?? p.images[0];
  return (
    <div className="space-y-3">
      <div
        className="relative overflow-hidden rounded-3xl border bg-white p-6 dark:bg-muted/40"
        onMouseMove={(event) => {
          if (!image) return;
          const box = event.currentTarget.getBoundingClientRect();
          setZoom({
            x: ((event.clientX - box.left) / box.width) * 100,
            y: ((event.clientY - box.top) / box.height) * 100,
          });
        }}
        onMouseLeave={() => setZoom(null)}
      >
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={image?.id ?? "art"}
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3, ease: EASE_OUT }}
            style={zoom ? { transformOrigin: `${zoom.x}% ${zoom.y}%` } : undefined}
            className={cn("transition-transform duration-200", zoom && "scale-[1.8]")}
          >
            <ProductImage
              url={image?.url}
              line={p.product_line}
              alt={p.name}
              className="w-full bg-transparent"
            />
          </motion.div>
        </AnimatePresence>
      </div>
      {p.images.length > 1 ? (
        <div className="flex gap-2">
          {p.images.map((img, index) => (
            <button
              key={img.id}
              type="button"
              aria-label={`Show image ${index + 1}`}
              aria-pressed={index === selected}
              onClick={() => setSelected(index)}
              className={cn(
                "size-20 overflow-hidden rounded-xl border bg-white p-1 transition dark:bg-muted/40",
                index === selected ? "ring-2 ring-brand" : "opacity-70 hover:opacity-100",
              )}
            >
              <ProductImage url={img.url} line={p.product_line} alt="" className="size-full" />
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** Same category first, topped up with best sellers. */
function Related({ product: p }: { product: ProductOut }) {
  const sameLine = useQuery(listProductsOptions({ query: { product_line: p.product_line } }));
  const best = useQuery(listProductsOptions({ query: { sort: "best_selling" } }));
  const seen = new Set([p.sku]);
  const items = [...(sameLine.data ?? []), ...(best.data ?? [])].filter((x) => {
    if (seen.has(x.sku)) return false;
    seen.add(x.sku);
    return true;
  });
  return (
    <ProductRail
      title="You may also like"
      items={items.slice(0, 8)}
      loading={sameLine.isPending || best.isPending}
    />
  );
}
