"use client";

import { Area, AreaChart, Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type ChartConfig,
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import type { DistributionItem, VolumePoint } from "@/lib/api/generated/types.gen";
import { cn } from "@/lib/utils";

export function KpiCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "danger" | "warning" | "good";
}) {
  return (
    <Card className="gap-1 py-4">
      <CardHeader className="px-4">
        <CardDescription>{label}</CardDescription>
        <CardTitle
          className={cn(
            "text-2xl tabular-nums",
            tone === "danger" && "text-red-600 dark:text-red-400",
            tone === "warning" && "text-amber-600 dark:text-amber-400",
            tone === "good" && "text-emerald-600 dark:text-emerald-400",
          )}
        >
          {value}
        </CardTitle>
      </CardHeader>
      {hint ? (
        <CardContent className="px-4 text-xs text-muted-foreground">{hint}</CardContent>
      ) : null}
    </Card>
  );
}

/** Horizontal bars in plain HTML: readable for long labels and many values. */
export function BarList({
  items,
  limit = 12,
  color = "var(--chart-1)",
}: {
  items: DistributionItem[];
  limit?: number;
  color?: string;
}) {
  if (!items.length) return <p className="text-sm text-muted-foreground">No data yet.</p>;
  const max = Math.max(...items.map((i) => i.count));
  const shown = items.slice(0, limit);
  return (
    <ul className="space-y-2">
      {shown.map((item) => (
        <li key={item.key} className="text-sm">
          <div className="mb-1 flex justify-between gap-2">
            <span className="truncate" title={item.label}>
              {item.label}
            </span>
            <span className="tabular-nums text-muted-foreground">
              {item.count}
              {item.pct != null ? ` · ${item.pct}%` : null}
            </span>
          </div>
          <div className="h-2 rounded-full bg-muted">
            <div
              className="h-2 rounded-full"
              style={{ width: `${(100 * item.count) / max}%`, background: color }}
            />
          </div>
        </li>
      ))}
      {items.length > limit ? (
        <li className="text-xs text-muted-foreground">+ {items.length - limit} more</li>
      ) : null}
    </ul>
  );
}

export function ChartCard({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

const VOLUME_CONFIG = {
  total: { label: "Complaints", color: "var(--chart-1)" },
  escalated: { label: "Escalated", color: "var(--chart-4)" },
  repeat: { label: "Repeat", color: "var(--chart-3)" },
} satisfies ChartConfig;

export function VolumeChart({ data }: { data: VolumePoint[] }) {
  if (!data.length) return <p className="text-sm text-muted-foreground">No data yet.</p>;
  const points = data.map((d) => ({
    ...d,
    label: new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" }).format(
      new Date(d.period),
    ),
  }));
  return (
    <ChartContainer config={VOLUME_CONFIG} className="aspect-auto h-64 w-full">
      <AreaChart data={points} margin={{ left: 0, right: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={24} />
        <YAxis width={32} tickLine={false} axisLine={false} allowDecimals={false} />
        <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
        <ChartLegend content={<ChartLegendContent />} />
        {(["total", "escalated", "repeat"] as const).map((key) => (
          <Area
            key={key}
            dataKey={key}
            type="monotone"
            stroke={`var(--color-${key})`}
            fill={`var(--color-${key})`}
            fillOpacity={key === "total" ? 0.2 : 0.1}
            strokeWidth={2}
          />
        ))}
      </AreaChart>
    </ChartContainer>
  );
}

const COUNT_CONFIG = {
  count: { label: "Complaints", color: "var(--chart-1)" },
} satisfies ChartConfig;

export function ColumnChart({ items, limit = 12 }: { items: DistributionItem[]; limit?: number }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">No data yet.</p>;
  return (
    <ChartContainer config={COUNT_CONFIG} className="aspect-auto h-64 w-full">
      <BarChart data={items.slice(0, limit)} margin={{ left: 0, right: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          interval={0}
          tickFormatter={(v: string) => (v.length > 12 ? `${v.slice(0, 11)}…` : v)}
        />
        <YAxis width={32} tickLine={false} axisLine={false} allowDecimals={false} />
        <ChartTooltip content={<ChartTooltipContent hideIndicator />} />
        <Bar dataKey="count" fill="var(--color-count)" radius={4} />
      </BarChart>
    </ChartContainer>
  );
}
