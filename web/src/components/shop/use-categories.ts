"use client";

import { useQuery } from "@tanstack/react-query";

import { PRODUCT_LINES } from "@/components/shop/lines";
import { listProductsOptions } from "@/lib/api/generated/@tanstack/react-query.gen";

export type Category = { code: string; label: string; count: number; cover?: string };

/** Product lines with their product counts and a cover photo (first product with images). */
export function useCategories(): Category[] {
  const products = useQuery(listProductsOptions());
  const all = products.data ?? [];
  return PRODUCT_LINES.map((line) => {
    const inLine = all.filter((p) => p.product_line === line.code);
    return {
      ...line,
      count: inLine.length,
      cover: inLine.find((p) => p.images.length)?.images[0]?.url,
    };
  });
}
