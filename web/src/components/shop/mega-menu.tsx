"use client";

import { ArrowRight, ChevronDown } from "lucide-react";
import Link from "next/link";

import { ProductImage } from "@/components/shop/product-image";
import { useCategories } from "@/components/shop/use-categories";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/** Shop menu: a tile per category (with a real product photo when one exists). */
export function ShopMegaMenu() {
  const categories = useCategories();

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-1">
          Shop <ChevronDown className="size-3.5 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" sideOffset={10} className="w-[min(92vw,640px)] p-3">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {categories.map((line) => (
            <DropdownMenuItem key={line.code} asChild className="p-0">
              <Link
                href={`/shop?line=${line.code}`}
                className="group flex flex-col items-stretch gap-2 rounded-xl p-2"
              >
                <div className="overflow-hidden rounded-lg bg-muted/50">
                  <ProductImage
                    url={line.cover}
                    line={line.code}
                    alt=""
                    className="w-full transition-transform duration-300 group-hover:scale-105"
                  />
                </div>
                <span className="text-sm font-medium">{line.label}</span>
                <span className="-mt-2 text-xs text-muted-foreground">{line.count} products</span>
              </Link>
            </DropdownMenuItem>
          ))}
        </div>
        <DropdownMenuItem asChild className="mt-2 justify-center">
          <Link href="/shop" className="font-medium text-brand">
            View all products <ArrowRight />
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
