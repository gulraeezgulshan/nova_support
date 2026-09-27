"use client";

import { Minus, Plus, ShoppingBag, Trash2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";

import { Reveal } from "@/components/motion/reveal";
import { MAX_QUANTITY } from "@/components/shop/cart-context";
import { OrderSummary } from "@/components/shop/order-summary";
import { ProductCarousel } from "@/components/shop/product-carousel";
import { ProductImage } from "@/components/shop/product-image";
import { useCartItems } from "@/components/shop/use-cart-items";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatMoney } from "@/lib/format";

export default function CartPage() {
  const { cart, items, subtotal, loading } = useCartItems();

  if (loading && cart.lines.length)
    return (
      <div className="mx-auto max-w-7xl px-4 py-10">
        <Skeleton className="h-64 w-full rounded-3xl" />
      </div>
    );

  if (!items.length)
    return (
      <div className="space-y-20 py-16">
        <Reveal className="mx-auto max-w-md space-y-4 px-4 text-center">
          <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-brand-soft">
            <ShoppingBag className="size-7 text-brand" />
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">Your cart is empty</h1>
          <p className="text-muted-foreground">Find something you&apos;ll love.</p>
          <Button asChild size="lg" className="rounded-full bg-brand text-brand-foreground">
            <Link href="/shop">Browse the shop</Link>
          </Button>
        </Reveal>
        <ProductCarousel title="Best sellers" sort="best_selling" href="/shop?sort=best_selling" />
      </div>
    );

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <Reveal>
        <h1 className="mb-8 text-4xl font-semibold tracking-tight">Your cart</h1>
      </Reveal>
      <div className="grid gap-10 lg:grid-cols-[1fr_24rem]">
        <ul className="h-fit divide-y rounded-3xl border">
          <AnimatePresence initial={false}>
            {items.map(({ product, quantity }) => (
              <motion.li
                key={product.sku}
                layout
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.25 }}
                className="flex items-center gap-4 overflow-hidden p-4 sm:p-5"
              >
                <Link
                  href={`/shop/${product.sku}`}
                  className="shrink-0 rounded-2xl border bg-white p-2 dark:bg-muted/40"
                >
                  <ProductImage
                    url={product.images[0]?.url}
                    line={product.product_line}
                    alt={product.name}
                    className="size-20 bg-transparent sm:size-24"
                  />
                </Link>
                <div className="flex min-w-0 flex-1 flex-col gap-3 sm:flex-row sm:items-center">
                  <div className="min-w-0 flex-1">
                    <Link href={`/shop/${product.sku}`} className="font-medium hover:underline">
                      {product.name}
                    </Link>
                    <p className="text-sm text-muted-foreground">
                      {formatMoney(product.price)} each
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center rounded-full border">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 rounded-full"
                        aria-label={`One fewer ${product.name}`}
                        disabled={quantity <= 1}
                        onClick={() => cart.setQuantity(product.sku, quantity - 1)}
                      >
                        <Minus />
                      </Button>
                      <span className="w-6 text-center text-sm tabular-nums">{quantity}</span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 rounded-full"
                        aria-label={`One more ${product.name}`}
                        disabled={quantity >= MAX_QUANTITY}
                        onClick={() => cart.setQuantity(product.sku, quantity + 1)}
                      >
                        <Plus />
                      </Button>
                    </div>
                    <span className="w-24 text-right font-semibold tabular-nums">
                      {formatMoney(product.price * quantity)}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove ${product.name}`}
                      onClick={() => cart.remove(product.sku)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </div>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
        <OrderSummary subtotal={subtotal} shippingNote="Chosen at checkout">
          <Button
            asChild
            size="lg"
            className="h-12 w-full rounded-full bg-brand text-brand-foreground hover:bg-brand/90"
          >
            <Link href="/checkout">Go to checkout</Link>
          </Button>
          <Button asChild variant="ghost" className="w-full">
            <Link href="/shop">Continue shopping</Link>
          </Button>
        </OrderSummary>
      </div>
    </div>
  );
}
