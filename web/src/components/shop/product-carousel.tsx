"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useReducedMotion } from "motion/react";
import { useRef } from "react";

import { Reveal } from "@/components/motion/reveal";
import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { ProductCard } from "@/components/shop/product-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { listProductsOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ProductOut } from "@/lib/api/generated/types.gen";

type Sort = "featured" | "price_asc" | "price_desc" | "newest" | "best_selling";

/** A titled row of product cards fed by a catalogue query. */
export function ProductCarousel({
  sort,
  limit = 8,
  exclude,
  productLine,
  ...rail
}: {
  title: string;
  subtitle?: string;
  href?: string;
  sort: Sort;
  limit?: number;
  exclude?: string;
  productLine?: string;
}) {
  const products = useQuery(
    listProductsOptions({
      query: productLine ? { sort, product_line: productLine } : { sort },
    }),
  );
  const items = (products.data ?? []).filter((p) => p.sku !== exclude).slice(0, limit);
  return <ProductRail {...rail} items={items} loading={products.isPending} />;
}

/** A titled, horizontally scrolling row of product cards. */
export function ProductRail({
  title,
  subtitle,
  href,
  items,
  loading = false,
}: {
  title: string;
  subtitle?: string;
  href?: string;
  items: ProductOut[];
  loading?: boolean;
}) {
  const rail = useRef<HTMLDivElement>(null);
  const still = useReducedMotion();
  const scroll = (direction: 1 | -1) =>
    rail.current?.scrollBy({
      left: direction * rail.current.clientWidth * 0.8,
      behavior: still ? "auto" : "smooth",
    });

  if (!loading && !items.length) return null;

  return (
    <section className="mx-auto max-w-7xl space-y-6 px-4">
      <Reveal className="flex items-end justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-3xl font-semibold tracking-tight">{title}</h2>
          {subtitle ? <p className="text-muted-foreground">{subtitle}</p> : null}
        </div>
        <div className="flex items-center gap-2">
          {href ? (
            <Button asChild variant="link" className="hidden text-brand sm:inline-flex">
              <Link href={href}>
                View all <ArrowRight />
              </Link>
            </Button>
          ) : null}
          <Button
            variant="outline"
            size="icon"
            className="hidden rounded-full md:inline-flex"
            aria-label="Scroll left"
            onClick={() => scroll(-1)}
          >
            <ChevronLeft />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="hidden rounded-full md:inline-flex"
            aria-label="Scroll right"
            onClick={() => scroll(1)}
          >
            <ChevronRight />
          </Button>
        </div>
      </Reveal>
      {loading ? (
        <div className="flex gap-4 overflow-hidden">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-80 w-64 shrink-0 rounded-2xl" />
          ))}
        </div>
      ) : (
        <div
          ref={rail}
          className="no-scrollbar -mx-4 snap-x snap-mandatory overflow-x-auto px-4 pb-4"
        >
          <Stagger className="flex gap-4">
            {items.map((p) => (
              <StaggerItem key={p.sku} className="w-64 shrink-0 snap-start sm:w-72">
                <ProductCard product={p} />
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      )}
    </section>
  );
}
