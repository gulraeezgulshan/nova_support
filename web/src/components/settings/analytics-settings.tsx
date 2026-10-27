"use client";

import { Field, NumberInput } from "@/components/settings/fields";
import type { AnalyticsSettings } from "@/lib/api/generated/types.gen";

function Checklist({
  options,
  selected,
  onChange,
}: {
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <div className="grid gap-1 rounded-md border p-2 text-xs sm:grid-cols-2">
      {options.map((code) => (
        <label key={code} className="flex items-center gap-2">
          <input
            type="checkbox"
            className="size-3.5 accent-primary"
            checked={selected.includes(code)}
            onChange={(e) =>
              onChange(e.target.checked ? [...selected, code] : selected.filter((c) => c !== code))
            }
          />
          <span className="font-mono">{code}</span>
        </label>
      ))}
    </div>
  );
}

const NUMBERS: {
  key:
    | "trend_window_days"
    | "trend_min_count"
    | "trend_rise_ratio"
    | "recurring_min_count"
    | "dashboard_list_limit";
  label: string;
  help: string;
  min: number;
  max: number;
  step?: number;
}[] = [
  {
    key: "trend_window_days",
    label: "Trend window (days)",
    help: "1 to 90. The latest window is compared with the one before.",
    min: 1,
    max: 90,
  },
  {
    key: "trend_min_count",
    label: "Minimum complaints for a trend",
    help: "1 to 100 in the latest window.",
    min: 1,
    max: 100,
  },
  {
    key: "trend_rise_ratio",
    label: "Rise ratio",
    help: "1.0 to 10. 1.5 means 50% more than the window before.",
    min: 1,
    max: 10,
    step: 0.1,
  },
  {
    key: "recurring_min_count",
    label: "Recurring product issue from",
    help: "1 to 100 complaints about the same product line and subcategory.",
    min: 1,
    max: 100,
  },
  {
    key: "dashboard_list_limit",
    label: "Dashboard list length",
    help: "5 to 50 rows in the SLA-risk and trend lists.",
    min: 5,
    max: 50,
  },
];

export function AnalyticsSettingsForm({
  value,
  defaults,
  onChange,
  categories,
  statuses,
}: {
  value: AnalyticsSettings;
  defaults: AnalyticsSettings;
  onChange: (patch: Partial<AnalyticsSettings>) => void;
  categories: string[];
  statuses: string[];
}) {
  return (
    <div className="space-y-6">
      {NUMBERS.map((n) => (
        <Field
          key={n.key}
          label={n.label}
          help={n.help}
          defaultText={String(defaults[n.key])}
          onReset={() => onChange({ [n.key]: defaults[n.key] })}
        >
          <NumberInput
            value={value[n.key]}
            min={n.min}
            max={n.max}
            step={n.step}
            onChange={(v) => onChange({ [n.key]: v })}
          />
        </Field>
      ))}
      <Field
        label="Watched categories"
        help="Any rise is reported for these (every category is checked anyway)."
        defaultText={defaults.watched_categories.join(", ") || "none"}
        onReset={() => onChange({ watched_categories: defaults.watched_categories })}
      >
        <Checklist
          options={categories}
          selected={value.watched_categories}
          onChange={(watched_categories) => onChange({ watched_categories })}
        />
      </Field>
      <Field
        label="Statuses that count as a first response"
        help="The SLA response clock stops when a complaint first reaches one of these."
        defaultText={defaults.first_response_statuses.join(", ")}
        onReset={() => onChange({ first_response_statuses: defaults.first_response_statuses })}
      >
        <Checklist
          options={statuses}
          selected={value.first_response_statuses}
          onChange={(first_response_statuses) => onChange({ first_response_statuses })}
        />
      </Field>
      <Field
        label="Statuses that stop the resolution clock"
        help="At least one."
        defaultText={defaults.resolved_statuses.join(", ")}
        onReset={() => onChange({ resolved_statuses: defaults.resolved_statuses })}
      >
        <Checklist
          options={statuses}
          selected={value.resolved_statuses}
          onChange={(resolved_statuses) => onChange({ resolved_statuses })}
        />
      </Field>
    </div>
  );
}
