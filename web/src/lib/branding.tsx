"use client";

import { useQuery } from "@tanstack/react-query";

import { readBrandingOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import { API_URL } from "@/lib/api/runtime-config";
import { cn } from "@/lib/utils";

export function useBranding() {
  return useQuery({ ...readBrandingOptions(), staleTime: 60_000 });
}

/**
 * Two letters for the badge: the capitals of the first word ("VoltHaven" → VH,
 * "SupportNova" → SN), else the first letters of the first two words, else two letters.
 */
export function initialsOf(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const capitals = (words[0] ?? "").match(/[A-Z]/g) ?? [];
  if (capitals.length >= 2) return capitals.slice(0, 2).join("");
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  return (words[0] ?? "?").slice(0, 2).toUpperCase();
}

/** The uploaded logo, or the initials badge when there is none. */
export function BrandMark({
  target,
  className,
}: {
  target: "shop" | "console";
  className?: string;
}) {
  const { data } = useBranding();
  const name =
    (target === "shop" ? data?.shop_name : data?.console_name) ??
    (target === "shop" ? "VoltHaven" : "SupportNova");
  const url = target === "shop" ? data?.shop_logo_url : data?.console_logo_url;
  if (url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- served by the API host
      <img
        src={`${API_URL}${url}`}
        alt={`${name} logo`}
        className={cn("size-8 rounded-lg object-contain", className)}
      />
    );
  }
  const initials = initialsOf(name);
  return (
    <span
      className={cn(
        "flex size-8 items-center justify-center rounded-lg text-xs font-bold",
        target === "shop"
          ? "bg-brand text-brand-foreground shadow-sm shadow-brand/30"
          : "bg-primary text-primary-foreground",
        className,
      )}
    >
      {initials}
    </span>
  );
}
