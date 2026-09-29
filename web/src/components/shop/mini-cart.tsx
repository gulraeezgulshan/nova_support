"use client";

import { Minus, Plus, ShoppingBag, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ProductImage } from "@/components/shop/product-image";
import { useCartItems } from "@/components/shop/use-cart-items";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Price } from "@/lib/currency";

/** Slide-in cart. Opened by the header button or `openCart()` from anywhere. */
export function MiniCart() {
  const [open, setOpen] = useState(false);
  const { cart, items, subtotal } = useCartItems();

  useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener("volthaven:open-cart", handler);
    return () => window.removeEventListener("volthaven:open-cart", handler);
  }, []);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent className="flex w-full flex-col gap-0 sm:max-w-md">
        <SheetHeader className="border-b">
          <SheetTitle>Your cart</SheetTitle>
          <SheetDescription>
            {cart.count ? `${cart.count} item${cart.count === 1 ? "" : "s"}` : "Nothing here yet"}
          </SheetDescription>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto p-4">
          {items.length ? (
            <ul className="space-y-4">
              <AnimatePresence initial={false}>
                {items.map(({ product, quantity }) => (
                  <motion.li
                    key={product.sku}
                    layout
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 40 }}
                    className="flex gap-3"
                  >
                    <ProductImage
                      url={product.images[0]?.url}
                      line={product.product_line}
                      alt={product.name}
                      className="size-20 shrink-0 rounded-lg border"
                    />
                    <div className="flex min-w-0 flex-1 flex-col gap-2">
                      <div className="flex items-start justify-between gap-2">
                        <Link
                          href={`/shop/${product.sku}`}
                          onClick={() => setOpen(false)}
                          className="line-clamp-2 text-sm font-medium hover:underline"
                        >
                          {product.name}
                        </Link>
                        <button
                          type="button"
                          aria-label={`Remove ${product.name}`}
                          className="text-muted-foreground hover:text-foreground"
                          onClick={() => cart.remove(product.sku)}
                        >
                          <X className="size-4" />
                        </button>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center rounded-full border">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-7 rounded-full"
                            aria-label="One fewer"
                            disabled={quantity <= 1}
                            onClick={() => cart.setQuantity(product.sku, quantity - 1)}
                          >
                            <Minus />
                          </Button>
                          <span className="w-6 text-center text-sm tabular-nums">{quantity}</span>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-7 rounded-full"
                            aria-label="One more"
                            disabled={quantity >= 5}
                            onClick={() => cart.setQuantity(product.sku, quantity + 1)}
                          >
                            <Plus />
                          </Button>
                        </div>
                        <span className="text-sm font-medium tabular-nums">
                          <Price usd={product.price * quantity} />
                        </span>
                      </div>
                    </div>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
              <ShoppingBag className="size-10 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Your cart is empty.</p>
              <Button asChild variant="outline" onClick={() => setOpen(false)}>
                <Link href="/shop">Browse the shop</Link>
              </Button>
            </div>
          )}
        </div>
        {items.length ? (
          <SheetFooter className="border-t">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Subtotal</span>
              <span className="text-base font-semibold tabular-nums">
                <Price usd={subtotal} />
              </span>
            </div>
            <Button asChild size="lg" className="bg-brand text-brand-foreground hover:bg-brand/90">
              <Link href="/checkout" onClick={() => setOpen(false)}>
                Checkout
              </Link>
            </Button>
            <Button asChild variant="outline" onClick={() => setOpen(false)}>
              <Link href="/cart">View cart</Link>
            </Button>
          </SheetFooter>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
