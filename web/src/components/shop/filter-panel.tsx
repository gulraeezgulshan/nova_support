"use client";

import { Check } from "lucide-react";

import type { Category } from "@/components/shop/use-categories";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export type Filters = { line?: string; min?: string; max?: string };

export const PRICE_PRESETS: { label: string; min?: string; max?: string }[] = [
  { label: "Under $50", max: "50" },
  { label: "$50 – $200", min: "50", max: "200" },
  { label: "$200 – $500", min: "200", max: "500" },
  { label: "$500 and up", min: "500" },
];

/** Category and price filters (sidebar on desktop, inside a sheet on phones). */
export function FilterPanel({
  categories,
  total,
  filters,
  onChange,
}: {
  categories: Category[];
  total: number;
  filters: Filters;
  onChange: (next: Filters) => void;
}) {
  const active = Boolean(filters.line || filters.min || filters.max);
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Category</h3>
        <ul className="space-y-0.5">
          <FilterOption
            label="All products"
            count={total}
            selected={!filters.line}
            onClick={() => onChange({ ...filters, line: undefined })}
          />
          {categories.map((c) => (
            <FilterOption
              key={c.code}
              label={c.label}
              count={c.count}
              selected={filters.line === c.code}
              onClick={() => onChange({ ...filters, line: c.code })}
            />
          ))}
        </ul>
      </div>
      <div className="space-y-3">
        <h3 className="text-sm font-semibold">Price</h3>
        <ul className="space-y-0.5">
          {PRICE_PRESETS.map((preset) => (
            <FilterOption
              key={preset.label}
              label={preset.label}
              selected={filters.min === preset.min && filters.max === preset.max}
              onClick={() => onChange({ ...filters, min: preset.min, max: preset.max })}
            />
          ))}
        </ul>
        <form
          key={`${filters.min ?? ""}-${filters.max ?? ""}`}
          className="flex items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            const value = (name: string) => String(data.get(name) ?? "").trim() || undefined;
            onChange({ ...filters, min: value("min"), max: value("max") });
          }}
        >
          <Input
            name="min"
            type="number"
            min={0}
            inputMode="numeric"
            placeholder="Min"
            aria-label="Minimum price"
            defaultValue={filters.min}
            className="h-8"
          />
          <span className="text-muted-foreground">–</span>
          <Input
            name="max"
            type="number"
            min={0}
            inputMode="numeric"
            placeholder="Max"
            aria-label="Maximum price"
            defaultValue={filters.max}
            className="h-8"
          />
          <Button type="submit" size="sm" variant="outline" className="h-8">
            Go
          </Button>
        </form>
      </div>
      {active ? (
        <Button variant="ghost" size="sm" className="px-0 text-brand" onClick={() => onChange({})}>
          Clear all filters
        </Button>
      ) : null}
    </div>
  );
}

function FilterOption({
  label,
  count,
  selected,
  onClick,
}: {
  label: string;
  count?: number;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        aria-pressed={selected}
        onClick={onClick}
        className={cn(
          "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition-colors hover:bg-muted",
          selected && "bg-brand-soft font-medium text-foreground",
        )}
      >
        <span className="flex size-4 items-center justify-center">
          {selected ? <Check className="size-3.5 text-brand" /> : null}
        </span>
        <span className="flex-1">{label}</span>
        {count !== undefined ? (
          <span className="text-xs text-muted-foreground tabular-nums">{count}</span>
        ) : null}
      </button>
    </li>
  );
}
