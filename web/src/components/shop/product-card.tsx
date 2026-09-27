"use client";

import { Plus } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { toast } from "sonner";

import { useCart } from "@/components/shop/cart-context";
import { flyToCart } from "@/components/shop/fly-to-cart";
import { PRODUCT_LINES } from "@/components/shop/lines";
import { ProductImage } from "@/components/shop/product-image";
import { Button } from "@/components/ui/button";
import type { ProductOut } from "@/lib/api/generated/types.gen";
import { formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";

const LABELS = Object.fromEntries(PRODUCT_LINES.map((l) => [l.code, l.label]));

export function ProductCard({ product, className }: { product: ProductOut; className?: string }) {
  const cart = useCart();
  return (
    <motion.article
      whileHover={{ y: -4 }}
      transition={{ type: "spring", stiffness: 300, damping: 24 }}
      className={cn(
        "group flex h-full flex-col overflow-hidden rounded-2xl border bg-card transition-shadow hover:shadow-xl hover:shadow-black/5",
        className,
      )}
    >
      <Link
        href={`/shop/${product.sku}`}
        aria-label={product.name}
        className="relative overflow-hidden bg-white p-4 dark:bg-muted/40"
      >
        <ProductImage
          url={product.images[0]?.url}
          line={product.product_line}
          alt={product.name}
          className="w-full rounded-none bg-transparent transition-transform duration-500 group-hover:scale-105"
        />
      </Link>
      <div className="flex flex-1 flex-col gap-1 p-4">
        <p className="text-xs font-medium tracking-wide text-brand uppercase">
          {LABELS[product.product_line] ?? product.product_line}
        </p>
        <Link href={`/shop/${product.sku}`} className="line-clamp-1 font-medium hover:underline">
          {product.name}
        </Link>
        <p className="line-clamp-1 text-xs text-muted-foreground">{product.specs[0]}</p>
        <div className="mt-auto flex items-center justify-between pt-3">
          <span className="text-lg font-semibold tabular-nums">{formatMoney(product.price)}</span>
          <Button
            size="sm"
            className="rounded-full bg-brand text-brand-foreground hover:bg-brand/90"
            onClick={(event) => {
              flyToCart(event.currentTarget);
              cart.add(product.sku);
              toast.success(`${product.name} added to your cart`);
            }}
          >
            <Plus /> Add
          </Button>
        </div>
      </div>
    </motion.article>
  );
}
