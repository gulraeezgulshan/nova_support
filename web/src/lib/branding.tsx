"use client";

import { useQuery } from "@tanstack/react-query";

import { readBrandingOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import { API_URL } from "@/lib/api/runtime-config";
import { cn } from "@/lib/utils";

export function useBranding() {
  return useQuery({ ...readBrandingOptions(), staleTime: 60_000 });
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
  const initials = name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
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
