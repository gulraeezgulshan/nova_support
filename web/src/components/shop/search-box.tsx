"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { ProductImage } from "@/components/shop/product-image";
import { Input } from "@/components/ui/input";
import { listProductsOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import { Price } from "@/lib/currency";
import { cn } from "@/lib/utils";

/** Catalogue search with instant suggestions; Enter shows all results on /shop. */
export function SearchBox({ className, onDone }: { className?: string; onDone?: () => void }) {
  const router = useRouter();
  const [term, setTerm] = useState("");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const results = useQuery({
    ...listProductsOptions({ query: { q: query } }),
    enabled: query.length >= 2,
  });
  const suggestions = (results.data ?? []).slice(0, 5);

  const finish = () => {
    setOpen(false);
    setTerm("");
    setQuery("");
    onDone?.();
  };

  return (
    <form
      role="search"
      className={cn("relative", className)}
      onSubmit={(event) => {
        event.preventDefault();
        if (!term.trim()) return;
        router.push(`/shop?q=${encodeURIComponent(term.trim())}`);
        finish();
      }}
    >
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        type="search"
        value={term}
        placeholder="Search products"
        aria-label="Search products"
        className="h-9 rounded-full bg-muted/60 pl-9"
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onChange={(event) => {
          const value = event.target.value;
          setTerm(value);
          setOpen(true);
          clearTimeout(timer.current);
          timer.current = setTimeout(() => setQuery(value.trim()), 200);
        }}
      />
      <AnimatePresence>
        {open && query.length >= 2 ? (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            className="absolute top-11 right-0 z-50 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-xl border bg-popover p-1 shadow-xl"
          >
            {suggestions.length ? (
              suggestions.map((p) => (
                <Link
                  key={p.sku}
                  href={`/shop/${p.sku}`}
                  onClick={finish}
                  className="flex items-center gap-3 rounded-lg p-2 text-sm hover:bg-muted"
                >
                  <ProductImage
                    url={p.images[0]?.url}
                    line={p.product_line}
                    alt=""
                    className="size-10 shrink-0 rounded-md"
                  />
                  <span className="line-clamp-1 flex-1">{p.name}</span>
                  <span className="tabular-nums text-muted-foreground">
                    <Price usd={p.price} />
                  </span>
                </Link>
              ))
            ) : (
              <p className="p-3 text-sm text-muted-foreground">
                {results.isPending ? "Searching…" : `No products match “${query}”.`}
              </p>
            )}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </form>
  );
}
