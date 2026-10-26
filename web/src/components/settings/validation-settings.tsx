"use client";

import { Plus, Trash2, TriangleAlert } from "lucide-react";

import { Field, NumberInput } from "@/components/settings/fields";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  CategoryOut,
  CompensationLimit,
  OperationsSettings,
  SignalBoost,
  ValidationSettings as Validation,
} from "@/lib/api/generated/types.gen";

const COMPENSATION_LABELS: Record<string, string> = {
  store_credit: "Store credit",
  shipping_fee_refund: "Shipping fee refund",
  partial_refund: "Partial refund",
  full_refund: "Full refund",
  replacement: "Replacement",
  repair: "Repair",
  voucher: "Voucher",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-5 border-t pt-5 first:border-t-0 first:pt-0">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

/** A scrollable list of checkboxes for picking codes. */
function CodeChecklist({
  options,
  selected,
  onChange,
}: {
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <div className="grid max-h-56 gap-1 overflow-y-auto rounded-md border p-2 text-xs sm:grid-cols-2">
      {options.map((code) => (
        <label key={code} className="flex items-center gap-2">
          <input
            type="checkbox"
            className="size-3.5 accent-primary"
            checked={selected.includes(code)}
            onChange={(e) =>
              onChange(
                e.target.checked ? [...selected, code] : selected.filter((c) => c !== code),
              )
            }
          />
          <span className="font-mono">{code}</span>
        </label>
      ))}
    </div>
  );
}

/** A number with a "no limit" switch (null). */
function OptionalLimit({
  value,
  max,
  unit,
  onChange,
}: {
  value: number | null | undefined;
  max: number;
  unit: string;
  onChange: (v: number | null) => void;
}) {
  const none = value === null || value === undefined;
  return (
    <div className="flex items-center gap-2">
      <div className="w-24">
        {none ? (
          <span className="text-xs text-muted-foreground">No limit</span>
        ) : (
          <NumberInput value={value} min={0} max={max} onChange={onChange} />
        )}
      </div>
      <span className="text-xs text-muted-foreground">{unit}</span>
      <label className="flex items-center gap-1 text-xs">
        <input
          type="checkbox"
          className="size-3.5 accent-primary"
          checked={none}
          onChange={(e) => onChange(e.target.checked ? null : 0)}
        />
        no limit
      </label>
    </div>
  );
}

export function ValidationSettingsForm({
  value,
  defaults,
  operations,
  operationsDefaults,
  onChange,
  onOperationsChange,
  actionCodes,
  categories,
  riskSignals,
}: {
  value: Validation;
  defaults: Validation;
  operations: OperationsSettings;
  operationsDefaults: OperationsSettings;
  onChange: (patch: Partial<Validation>) => void;
  onOperationsChange: (patch: Partial<OperationsSettings>) => void;
  actionCodes: string[];
  categories: CategoryOut[];
  riskSignals: string[];
}) {
  const w = value.score_weights;
  const dw = defaults.score_weights;
  const setComp = (kind: string, patch: Partial<CompensationLimit>) =>
    onChange({
      compensation: { ...value.compensation, [kind]: { ...value.compensation[kind], ...patch } },
    });
  const setBoost = (signal: string, patch: Partial<SignalBoost>) =>
    onChange({
      signal_boosts: { ...value.signal_boosts, [signal]: { ...value.signal_boosts[signal], ...patch } },
    });
  const renameBoost = (from: string, to: string) => {
    const next: Record<string, SignalBoost> = {};
    for (const [k, v] of Object.entries(value.signal_boosts)) next[k === from ? to : k] = v;
    onChange({ signal_boosts: next });
  };
  const subsOf = (category: string) =>
    categories.find((c) => c.code === category)?.subcategories.map((s) => s.code) ?? [];
  const removedGuards = defaults.never_allowed_actions.filter(
    (c) => !value.never_allowed_actions.includes(c),
  );
  const unusedSignals = riskSignals.filter((s) => !(s in value.signal_boosts));

  return (
    <div className="space-y-8">
      <Section title="Verdict">
        <Field
          label="Check weights (critical / major / minor)"
          help="Points each check is worth by severity, 1 to 10, critical ≥ major ≥ minor."
          defaultText={`${dw.critical} / ${dw.major} / ${dw.minor}`}
          onReset={() => onChange({ score_weights: dw })}
        >
          <div className="grid grid-cols-3 gap-2">
            {(["critical", "major", "minor"] as const).map((k) => (
              <NumberInput
                key={k}
                value={w[k]}
                min={1}
                max={10}
                onChange={(v) => onChange({ score_weights: { ...w, [k]: v } })}
              />
            ))}
          </div>
        </Field>
        <Field
          label="Minimum score for 'verified'"
          help="50 to 100 (also on the Operations tab)."
          defaultText={String(operationsDefaults.verified_min_score)}
          onReset={() =>
            onOperationsChange({ verified_min_score: operationsDefaults.verified_min_score })
          }
        >
          <NumberInput
            value={operations.verified_min_score}
            min={50}
            max={100}
            onChange={(v) => onOperationsChange({ verified_min_score: v })}
          />
        </Field>
        <Field
          label="Always review from escalation level"
          help="1 to 5 (also on the Operations tab)."
          defaultText={String(operationsDefaults.always_review_escalation_level)}
          onReset={() =>
            onOperationsChange({
              always_review_escalation_level: operationsDefaults.always_review_escalation_level,
            })
          }
        >
          <NumberInput
            value={operations.always_review_escalation_level}
            min={1}
            max={5}
            onChange={(v) => onOperationsChange({ always_review_escalation_level: v })}
          />
        </Field>
      </Section>

      <Section title="Compensation">
        <p className="text-xs text-muted-foreground">
          The most the AI may offer, and which rule actions must be required for it to be allowed.
        </p>
        {Object.keys(COMPENSATION_LABELS).map((kind) => {
          const limit = value.compensation[kind];
          const d = defaults.compensation[kind];
          if (!limit) return null;
          return (
            <Field
              key={kind}
              label={COMPENSATION_LABELS[kind]}
              defaultText={`${d.max_pct_of_order ?? "no limit"} % · ${d.max_amount ?? "no limit"} USD`}
              onReset={() => setComp(kind, d)}
            >
              <div className="space-y-2">
                <OptionalLimit
                  value={limit.max_pct_of_order}
                  max={100}
                  unit="% of order"
                  onChange={(v) => setComp(kind, { max_pct_of_order: v })}
                />
                <OptionalLimit
                  value={limit.max_amount}
                  max={10000}
                  unit="USD"
                  onChange={(v) => setComp(kind, { max_amount: v })}
                />
                <details className="text-xs">
                  <summary className="cursor-pointer text-muted-foreground">
                    Allowed when the rules require one of: {limit.requires_any.join(", ")}
                  </summary>
                  <CodeChecklist
                    options={actionCodes}
                    selected={limit.requires_any}
                    onChange={(next) => setComp(kind, { requires_any: next })}
                  />
                </details>
              </div>
            </Field>
          );
        })}
      </Section>

      <Section title="Never-allowed actions">
        <Field
          label="The AI may never propose"
          help="Removed from every plan, whatever the rules say."
          defaultText={`${defaults.never_allowed_actions.length} actions`}
          onReset={() => onChange({ never_allowed_actions: defaults.never_allowed_actions })}
        >
          <CodeChecklist
            options={actionCodes}
            selected={value.never_allowed_actions}
            onChange={(next) => onChange({ never_allowed_actions: next })}
          />
          {removedGuards.length ? (
            <p className="mt-2 flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
              <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
              This removes a safety guard: the AI may then propose it. ({removedGuards.join(", ")})
            </p>
          ) : null}
        </Field>
      </Section>

      <Section title="Needs an order">
        <Field
          label="Categories that need an order"
          help="Without a linked order, the AI must ask for one."
          defaultText={defaults.orders_required_for.join(", ")}
          onReset={() => onChange({ orders_required_for: defaults.orders_required_for })}
        >
          <CodeChecklist
            options={categories.map((c) => c.code)}
            selected={value.orders_required_for}
            onChange={(next) => onChange({ orders_required_for: next })}
          />
        </Field>
      </Section>

      <Section title="Escalation action levels">
        {Object.keys(defaults.escalation_action_levels).map((code) => (
          <Field
            key={code}
            label={code}
            help="Counts as done when the AI's escalation reaches this level (1 to 5)."
            defaultText={String(defaults.escalation_action_levels[code])}
            onReset={() =>
              onChange({
                escalation_action_levels: {
                  ...value.escalation_action_levels,
                  [code]: defaults.escalation_action_levels[code],
                },
              })
            }
          >
            <NumberInput
              value={value.escalation_action_levels[code]}
              min={1}
              max={5}
              onChange={(v) =>
                onChange({
                  escalation_action_levels: { ...value.escalation_action_levels, [code]: v },
                })
              }
            />
          </Field>
        ))}
      </Section>

      <Section title="Classifier">
        <Field
          label="Score needed to name a category"
          help="1 to 10. Below this, Python says 'tentative' and does not judge the category."
          defaultText={String(defaults.classifier_confident)}
          onReset={() => onChange({ classifier_confident: defaults.classifier_confident })}
        >
          <NumberInput
            value={value.classifier_confident}
            min={1}
            max={10}
            onChange={(v) => onChange({ classifier_confident: v })}
          />
        </Field>
        <Field
          label="Score for a secondary issue"
          help="1 to 10."
          defaultText={String(defaults.classifier_secondary)}
          onReset={() => onChange({ classifier_secondary: defaults.classifier_secondary })}
        >
          <NumberInput
            value={value.classifier_secondary}
            min={1}
            max={10}
            onChange={(v) => onChange({ classifier_secondary: v })}
          />
        </Field>
        <Field
          label="Signal boosts"
          help="A detected risk signal adds this weight to a subcategory."
          defaultText={`${Object.keys(defaults.signal_boosts).length} boosts`}
          onReset={() => onChange({ signal_boosts: defaults.signal_boosts })}
        >
          <div className="space-y-2">
            {Object.entries(value.signal_boosts).map(([signal, boost]) => (
              <div
                key={signal}
                className="grid grid-cols-2 items-center gap-2 rounded-md border p-2 md:grid-cols-[1fr_1fr_1fr_4rem_auto] md:border-0 md:p-0"
              >
                <Select value={signal} onValueChange={(to) => renameBoost(signal, to)}>
                  <SelectTrigger aria-label="Signal" className="w-full min-w-0">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[signal, ...unusedSignals].map((s) => (
                      <SelectItem key={s} value={s}>
                        {s}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select
                  value={boost.category}
                  onValueChange={(c) =>
                    setBoost(signal, { category: c, subcategory: subsOf(c)[0] ?? "" })
                  }
                >
                  <SelectTrigger aria-label="Category" className="w-full min-w-0">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((c) => (
                      <SelectItem key={c.code} value={c.code}>
                        {c.code}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select
                  value={boost.subcategory}
                  onValueChange={(s) => setBoost(signal, { subcategory: s })}
                >
                  <SelectTrigger aria-label="Subcategory" className="w-full min-w-0">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {subsOf(boost.category).map((s) => (
                      <SelectItem key={s} value={s}>
                        {s}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <NumberInput
                  value={boost.weight}
                  min={1}
                  max={5}
                  onChange={(v) => setBoost(signal, { weight: v })}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove ${signal} boost`}
                  onClick={() => {
                    const next = { ...value.signal_boosts };
                    delete next[signal];
                    onChange({ signal_boosts: next });
                  }}
                >
                  <Trash2 />
                </Button>
              </div>
            ))}
            <Button
              variant="outline"
              size="sm"
              disabled={!unusedSignals.length || !categories.length}
              onClick={() => {
                const category = categories[0].code;
                onChange({
                  signal_boosts: {
                    ...value.signal_boosts,
                    [unusedSignals[0]]: { category, subcategory: subsOf(category)[0] ?? "", weight: 1 },
                  },
                });
              }}
            >
              <Plus /> Add boost
            </Button>
          </div>
        </Field>
      </Section>
    </div>
  );
}
