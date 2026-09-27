"use client";

import { useQuery } from "@tanstack/react-query";
import { SlidersHorizontal, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { Reveal } from "@/components/motion/reveal";
import { FilterPanel, type Filters, PRICE_PRESETS } from "@/components/shop/filter-panel";
import { PRODUCT_LINES } from "@/components/shop/lines";
import { ProductCard } from "@/components/shop/product-card";
import { useCategories } from "@/components/shop/use-categories";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { listProductsOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import { apiErrorMessage } from "@/lib/api/errors";

const SORTS = [
  { value: "featured", label: "Featured" },
  { value: "best_selling", label: "Best selling" },
  { value: "newest", label: "Newest" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
] as const;
type Sort = (typeof SORTS)[number]["value"];

function asSort(value: string | null): Sort {
  return SORTS.some((s) => s.value === value) ? (value as Sort) : "featured";
}

function asPrice(value: string | null): string | undefined {
  return value && /^\d+(\.\d+)?$/.test(value) ? value : undefined;
}

function Catalogue() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const categories = useCategories();
  const line = params.get("line") ?? undefined;
  const q = params.get("q")?.trim() || undefined;
  const sort = asSort(params.get("sort"));
  const min = asPrice(params.get("min"));
  const max = asPrice(params.get("max"));

  const update = (changes: Record<string, string | undefined>) => {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  };
  const setFilters = (f: Filters) => update({ line: f.line, min: f.min, max: f.max });

  const products = useQuery(
    listProductsOptions({
      query: {
        sort,
        ...(line ? { product_line: line } : {}),
        ...(q ? { q } : {}),
        ...(min ? { min_price: Number(min) } : {}),
        ...(max ? { max_price: Number(max) } : {}),
      },
    }),
  );
  const lineLabel = PRODUCT_LINES.find((l) => l.code === line)?.label;
  const priceLabel =
    PRICE_PRESETS.find((p) => p.min === min && p.max === max)?.label ??
    (min || max ? `$${min ?? 0} – ${max ? `$${max}` : "any"}` : undefined);
  const total = categories.reduce((n, c) => n + c.count, 0);
  const panel = (
    <FilterPanel
      categories={categories}
      total={total}
      filters={{ line, min, max }}
      onChange={setFilters}
    />
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <Reveal className="mb-8 space-y-2">
        <p className="text-sm text-muted-foreground">Shop</p>
        <h1 className="text-4xl font-semibold tracking-tight">
          {q ? `Results for “${q}”` : (lineLabel ?? "All products")}
        </h1>
      </Reveal>
      <div className="grid gap-10 lg:grid-cols-[220px_1fr]">
        <aside className="hidden lg:block">
          <div className="sticky top-24">{panel}</div>
        </aside>
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-2">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline" size="sm" className="lg:hidden">
                  <SlidersHorizontal /> Filters
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-80">
                <SheetHeader>
                  <SheetTitle>Filters</SheetTitle>
                </SheetHeader>
                <div className="px-4 pb-6">{panel}</div>
              </SheetContent>
            </Sheet>
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {products.data ? `${products.data.length} products` : " "}
            </p>
            {[
              q && { label: `“${q}”`, clear: () => update({ q: undefined }) },
              lineLabel && { label: lineLabel, clear: () => update({ line: undefined }) },
              priceLabel && {
                label: priceLabel,
                clear: () => update({ min: undefined, max: undefined }),
              },
            ]
              .filter((chip): chip is { label: string; clear: () => void } => Boolean(chip))
              .map((chip) => (
                <button
                  key={chip.label}
                  type="button"
                  onClick={chip.clear}
                  className="flex items-center gap-1 rounded-full border bg-muted/50 px-3 py-1 text-xs hover:bg-muted"
                  aria-label={`Remove filter ${chip.label}`}
                >
                  {chip.label} <X className="size-3" />
                </button>
              ))}
            <div className="ml-auto">
              <Select
                value={sort}
                onValueChange={(value) =>
                  update({ sort: value === "featured" ? undefined : value })
                }
              >
                <SelectTrigger size="sm" className="w-48" aria-label="Sort products">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent align="end">
                  {SORTS.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          {products.isPending ? (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
              {Array.from({ length: 6 }, (_, i) => (
                <Skeleton key={i} className="h-80 rounded-2xl" />
              ))}
            </div>
          ) : products.isError ? (
            <p className="text-sm text-destructive">{apiErrorMessage(products.error)}</p>
          ) : products.data.length ? (
            <motion.div layout className="grid grid-cols-2 gap-4 md:grid-cols-3">
              <AnimatePresence mode="popLayout" initial={false}>
                {products.data.map((p, i) => (
                  <motion.div
                    key={p.sku}
                    layout
                    initial={{ opacity: 0, scale: 0.96, y: 12 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.96 }}
                    transition={{ duration: 0.3, delay: Math.min(i, 8) * 0.03 }}
                  >
                    <ProductCard product={p} />
                  </motion.div>
                ))}
              </AnimatePresence>
            </motion.div>
          ) : (
            <div className="rounded-2xl border border-dashed p-12 text-center">
              <p className="font-medium">No products match these filters.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Try a different search or clear the filters.
              </p>
              <Button
                variant="outline"
                className="mt-4 rounded-full"
                onClick={() => router.replace(pathname, { scroll: false })}
              >
                Clear everything
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ShopPage() {
  return (
    <Suspense>
      <Catalogue />
    </Suspense>
  );
}
