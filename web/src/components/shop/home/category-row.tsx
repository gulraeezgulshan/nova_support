"use client";

import Link from "next/link";

import { Reveal } from "@/components/motion/reveal";
import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { ProductImage } from "@/components/shop/product-image";
import { useCategories } from "@/components/shop/use-categories";

export function CategoryRow() {
  const categories = useCategories();
  return (
    <section className="mx-auto max-w-7xl space-y-6 px-4">
      <Reveal className="space-y-1">
        <h2 className="text-3xl font-semibold tracking-tight">Shop by category</h2>
        <p className="text-muted-foreground">Everything you need, from pocket to living room.</p>
      </Reveal>
      <Stagger className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {categories.map((c) => (
          <StaggerItem key={c.code}>
            <Link
              href={`/shop?line=${c.code}`}
              className="group flex items-center gap-4 rounded-2xl border bg-card p-3 transition-all hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-lg hover:shadow-brand/5"
            >
              <div className="size-16 shrink-0 overflow-hidden rounded-xl bg-white dark:bg-muted/40">
                <ProductImage
                  url={c.cover}
                  line={c.code}
                  alt=""
                  className="size-16 bg-transparent transition-transform duration-300 group-hover:scale-110"
                />
              </div>
              <div>
                <p className="font-medium">{c.label}</p>
                <p className="text-xs text-muted-foreground">{c.count} products</p>
              </div>
            </Link>
          </StaggerItem>
        ))}
      </Stagger>
    </section>
  );
}
