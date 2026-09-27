import {
  Cable,
  Headphones,
  Home,
  Laptop,
  type LucideIcon,
  Router,
  Smartphone,
  Tablet,
  Watch,
} from "lucide-react";

import { cn } from "@/lib/utils";

const ART: Record<string, { icon: LucideIcon; tone: string }> = {
  SMARTPHONE: {
    icon: Smartphone,
    tone: "from-sky-500/20 to-sky-500/5 text-sky-700 dark:text-sky-300",
  },
  LAPTOP: {
    icon: Laptop,
    tone: "from-indigo-500/20 to-indigo-500/5 text-indigo-700 dark:text-indigo-300",
  },
  TABLET: {
    icon: Tablet,
    tone: "from-violet-500/20 to-violet-500/5 text-violet-700 dark:text-violet-300",
  },
  AUDIO: {
    icon: Headphones,
    tone: "from-rose-500/20 to-rose-500/5 text-rose-700 dark:text-rose-300",
  },
  WEARABLE: {
    icon: Watch,
    tone: "from-emerald-500/20 to-emerald-500/5 text-emerald-700 dark:text-emerald-300",
  },
  NETWORKING: {
    icon: Router,
    tone: "from-amber-500/20 to-amber-500/5 text-amber-700 dark:text-amber-300",
  },
  SMART_HOME: {
    icon: Home,
    tone: "from-teal-500/20 to-teal-500/5 text-teal-700 dark:text-teal-300",
  },
  ACCESSORY: {
    icon: Cable,
    tone: "from-slate-500/20 to-slate-500/5 text-slate-700 dark:text-slate-300",
  },
};

export function ProductArt({ line, className }: { line: string; className?: string }) {
  const { icon: Icon, tone } = ART[line] ?? ART.ACCESSORY;
  return (
    <div
      className={cn(
        "flex aspect-square items-center justify-center rounded-xl bg-gradient-to-br",
        tone,
        className,
      )}
    >
      <Icon className="size-1/3" strokeWidth={1.25} aria-hidden />
    </div>
  );
}
