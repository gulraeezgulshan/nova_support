"use client";

import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getVocabularyOptions,
  listCategoriesOptions,
  listDepartmentsOptions,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import { humanize } from "@/lib/format";

/** Filters shared by the dashboard, analytics and reports (mirrors `src/analytics/filters.py`). */
export type AnalyticsFilters = {
  date_from?: string;
  date_to?: string;
  category?: string;
  department?: string;
  priority?: string;
  sentiment?: string;
  channel?: string;
};

const ALL = "__all__";

/** Only the filters that are set, ready to pass as query parameters. */
export function filterQuery(filters: AnalyticsFilters): AnalyticsFilters {
  return Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) as AnalyticsFilters;
}

function Choice({
  value,
  placeholder,
  options,
  onChange,
  width = "w-40",
}: {
  value?: string;
  placeholder: string;
  options: { value: string; label: string }[];
  onChange: (value?: string) => void;
  width?: string;
}) {
  return (
    <Select value={value ?? ALL} onValueChange={(v) => onChange(v === ALL ? undefined : v)}>
      <SelectTrigger className={width} aria-label={placeholder}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{placeholder}</SelectItem>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function FilterBar({
  value,
  onChange,
}: {
  value: AnalyticsFilters;
  onChange: (value: AnalyticsFilters) => void;
}) {
  const categories = useQuery(listCategoriesOptions());
  const departments = useQuery(listDepartmentsOptions());
  const vocabulary = useQuery({ ...getVocabularyOptions(), staleTime: Infinity });
  const vocab = vocabulary.data;
  const set = (key: keyof AnalyticsFilters) => (v?: string) => onChange({ ...value, [key]: v });
  const active = Object.values(value).some(Boolean);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        type="date"
        className="w-40"
        aria-label="Submitted from"
        value={value.date_from ?? ""}
        onChange={(e) => set("date_from")(e.target.value || undefined)}
      />
      <span className="text-sm text-muted-foreground">to</span>
      <Input
        type="date"
        className="w-40"
        aria-label="Submitted to"
        value={value.date_to ?? ""}
        onChange={(e) => set("date_to")(e.target.value || undefined)}
      />
      <Choice
        value={value.category}
        placeholder="All categories"
        width="w-48"
        options={(categories.data ?? []).map((c) => ({ value: c.code, label: c.name }))}
        onChange={set("category")}
      />
      <Choice
        value={value.department}
        placeholder="All departments"
        width="w-48"
        options={(departments.data ?? []).map((d) => ({ value: d.code, label: d.name }))}
        onChange={set("department")}
      />
      <Choice
        value={value.priority}
        placeholder="All priorities"
        width="w-36"
        options={(vocab?.priorities ?? []).map((p) => ({ value: p, label: p }))}
        onChange={set("priority")}
      />
      <Choice
        value={value.sentiment}
        placeholder="All sentiments"
        options={(vocab?.sentiments ?? []).map((s) => ({ value: s, label: s }))}
        onChange={set("sentiment")}
      />
      <Choice
        value={value.channel}
        placeholder="All channels"
        options={(vocab?.channels ?? []).map((c) => ({ value: c, label: humanize(c) }))}
        onChange={set("channel")}
      />
      {active ? (
        <Button variant="ghost" size="sm" onClick={() => onChange({})}>
          <X /> Clear
        </Button>
      ) : null}
    </div>
  );
}
