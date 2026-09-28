import type { SVGProps } from "react";

import { cn } from "@/lib/utils";
import { ICONS, type IconKey } from "@/lib/stack-icons";

// Near-black brand colours (Next.js, Vercel, Railway…) follow the text colour so they stay
// visible in dark mode.
const DARK = new Set(["000000", "0B0D0E", "191919"]);

export function BrandLogo({
  icon,
  className,
  ...props
}: { icon: IconKey } & Omit<SVGProps<SVGSVGElement>, "fill">) {
  const { title, hex, path } = ICONS[icon];
  const dark = DARK.has(hex.toUpperCase());
  return (
    <svg
      viewBox="0 0 24 24"
      role="img"
      aria-label={title}
      className={cn(dark && "fill-foreground", className)}
      fill={dark ? undefined : `#${hex}`}
      {...props}
    >
      <path d={path} />
    </svg>
  );
}
