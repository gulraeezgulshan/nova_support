"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  createRuleMutation,
  getVocabularyOptions,
  listCategoriesOptions,
  listDepartmentsOptions,
  listFactsOptions,
  listRulesQueryKey,
  replaceRuleMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { RuleOut, RuleWrite } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

const NONE = "__none__";

const EMPTY: RuleWrite = {
  rule_id: "",
  rule_type: "resolution",
  description: "",
  category: null,
  subcategory: null,
  condition: "",
  department: null,
  supporting_departments: [],
  urgency: null,
  priority: null,
  escalation_level: 0,
  required_actions: [],
  prohibited_actions: [],
  policy_refs: [],
  follow_up_type: null,
  follow_up_hours: null,
  rule_priority: 50,
  is_active: true,
};

function toWrite(rule: RuleOut): RuleWrite {
  const write: RuleWrite & { version?: number } = { ...rule };
  delete write.version;
  return write;
}

/** Create a rule (`rule` omitted) or edit one. Everything is validated again by the API. */
export function RuleEditor({
  rule,
  open,
  onOpenChange,
}: {
  rule?: RuleOut;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{rule ? `Edit rule ${rule.rule_id}` : "New rule"}</DialogTitle>
          <DialogDescription>
            Changes apply to the next analysis and validation. Every change is versioned and
            audited.
          </DialogDescription>
        </DialogHeader>
        {open ? (
          <RuleForm
            key={rule?.rule_id ?? "new"}
            initial={rule ? toWrite(rule) : EMPTY}
            editing={Boolean(rule)}
            onDone={() => onOpenChange(false)}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

function Optional({
  value,
  onChange,
  options,
  none,
}: {
  value?: string | null;
  onChange: (value: string | null) => void;
  options: { value: string; label: string }[];
  none: string;
}) {
  return (
    <Select value={value ?? NONE} onValueChange={(v) => onChange(v === NONE ? null : v)}>
      <SelectTrigger className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NONE}>{none}</SelectItem>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function ChipPicker({
  options,
  value,
  onChange,
  tone,
}: {
  options: { value: string; label: string; title?: string }[];
  value: string[];
  onChange: (value: string[]) => void;
  tone?: "good" | "bad";
}) {
  const [filter, setFilter] = useState("");
  const shown = options.filter((o) => o.value.toLowerCase().includes(filter.toLowerCase()));
  const toggle = (v: string) =>
    onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  return (
    <div className="space-y-2 rounded-md border p-2">
      {options.length > 12 ? (
        <Input
          placeholder="Filter"
          className="h-8"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      ) : null}
      <div className="flex max-h-32 flex-wrap gap-1 overflow-y-auto">
        {shown.map((o) => {
          const on = value.includes(o.value);
          return (
            <button
              type="button"
              key={o.value}
              title={o.title}
              aria-pressed={on}
              onClick={() => toggle(o.value)}
              className={cn(
                "rounded-md border px-1.5 py-0.5 font-mono text-[11px] transition-colors",
                on
                  ? tone === "bad"
                    ? "border-red-600/50 bg-red-500/15 text-red-700 dark:text-red-400"
                    : "border-emerald-600/50 bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
                  : "text-muted-foreground hover:bg-muted",
              )}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function RuleForm({
  initial,
  editing,
  onDone,
}: {
  initial: RuleWrite;
  editing: boolean;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [rule, setRule] = useState<RuleWrite>(initial);
  const [policyRefs, setPolicyRefs] = useState((initial.policy_refs ?? []).join(", "));
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof RuleWrite>(key: K, value: RuleWrite[K]) =>
    setRule((r) => ({ ...r, [key]: value }));

  const vocabulary = useQuery({ ...getVocabularyOptions(), staleTime: Infinity });
  const categories = useQuery(listCategoriesOptions());
  const departments = useQuery(listDepartmentsOptions());
  const facts = useQuery(listFactsOptions());
  const vocab = vocabulary.data;

  const subcategories = useMemo(
    () => categories.data?.find((c) => c.code === rule.category)?.subcategories ?? [],
    [categories.data, rule.category],
  );
  const departmentOptions = (departments.data ?? []).map((d) => ({ value: d.code, label: d.name }));
  const actionOptions = (vocab?.actions ?? []).map((a) => ({
    value: a.code,
    label: a.code,
    title: `${a.kind}: ${a.description}`,
  }));

  const handlers = {
    onSuccess: () => {
      toast.success(editing ? "Rule updated" : "Rule created");
      queryClient.invalidateQueries({ queryKey: listRulesQueryKey() });
      onDone();
    },
    onError: (err: unknown) => setError(apiErrorMessage(err)),
  };
  const create = useMutation({ ...createRuleMutation(), ...handlers });
  const replace = useMutation({ ...replaceRuleMutation(), ...handlers });
  const pending = create.isPending || replace.isPending;

  function save() {
    setError(null);
    const body: RuleWrite = {
      ...rule,
      rule_id: rule.rule_id.trim().toUpperCase(),
      policy_refs: policyRefs
        .split(/[,\s]+/)
        .map((s) => s.trim())
        .filter(Boolean),
    };
    if (editing) replace.mutate({ path: { rule_id: body.rule_id }, body });
    else create.mutate({ body });
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Rule ID" hint="e.g. DEL-020 or ESC-040">
          <Input
            value={rule.rule_id}
            disabled={editing}
            onChange={(e) => set("rule_id", e.target.value)}
          />
        </Field>
        <Field label="Type">
          <Select
            value={rule.rule_type}
            onValueChange={(v) => set("rule_type", v as RuleWrite["rule_type"])}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="resolution">Resolution (per category)</SelectItem>
              <SelectItem value="escalation">Escalation (any complaint)</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="Rule priority" hint="Higher wins when several rules match">
          <Input
            type="number"
            value={rule.rule_priority ?? 50}
            onChange={(e) => set("rule_priority", Number(e.target.value))}
          />
        </Field>
      </div>

      <Field label="Description">
        <Input value={rule.description} onChange={(e) => set("description", e.target.value)} />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Category">
          <Optional
            value={rule.category}
            none="Any category"
            options={(categories.data ?? []).map((c) => ({ value: c.code, label: c.name }))}
            onChange={(v) => setRule((r) => ({ ...r, category: v, subcategory: null }))}
          />
        </Field>
        <Field label="Subcategory">
          <Optional
            value={rule.subcategory}
            none="Any subcategory"
            options={subcategories.map((s) => ({ value: s.code, label: s.name }))}
            onChange={(v) => set("subcategory", v)}
          />
        </Field>
      </div>

      <Field
        label="Condition"
        hint="Empty = always. Operators: and, or, not, comparisons, in. Click a fact to insert it."
      >
        <Textarea
          rows={2}
          className="font-mono text-xs"
          placeholder="days_late > 5 and shipping_method == 'standard'"
          value={rule.condition ?? ""}
          onChange={(e) => set("condition", e.target.value)}
        />
        <div className="flex max-h-24 flex-wrap gap-1 overflow-y-auto">
          {(facts.data ?? []).map((f) => (
            <button
              type="button"
              key={f.name}
              title={`${f.type}: ${f.description}`}
              className="rounded border px-1 font-mono text-[10px] text-muted-foreground hover:bg-muted"
              onClick={() =>
                set("condition", `${rule.condition ?? ""}${rule.condition ? " " : ""}${f.name}`)
              }
            >
              {f.name}
            </button>
          ))}
        </div>
      </Field>

      <div className="grid gap-4 sm:grid-cols-4">
        <Field label="Department">
          <Optional
            value={rule.department}
            none="Keep"
            options={departmentOptions}
            onChange={(v) => set("department", v)}
          />
        </Field>
        <Field label="Urgency">
          <Optional
            value={rule.urgency}
            none="Keep"
            options={(vocab?.urgencies ?? []).map((u) => ({ value: u, label: u }))}
            onChange={(v) => set("urgency", v)}
          />
        </Field>
        <Field label="Priority">
          <Optional
            value={rule.priority}
            none="Keep"
            options={(vocab?.priorities ?? []).map((p) => ({ value: p, label: p }))}
            onChange={(v) => set("priority", v)}
          />
        </Field>
        <Field label="Escalation">
          <Select
            value={String(rule.escalation_level ?? 0)}
            onValueChange={(v) => set("escalation_level", Number(v))}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(vocab?.escalation_levels ?? []).map((l) => (
                <SelectItem key={l.level} value={String(l.level)}>
                  L{l.level} · {l.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>

      <Field label="Supporting departments">
        <ChipPicker
          options={departmentOptions.map((d) => ({ ...d, label: d.value }))}
          value={rule.supporting_departments ?? []}
          onChange={(v) => set("supporting_departments", v)}
        />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Required actions">
          <ChipPicker
            options={actionOptions}
            value={rule.required_actions ?? []}
            onChange={(v) => set("required_actions", v)}
            tone="good"
          />
        </Field>
        <Field label="Prohibited actions">
          <ChipPicker
            options={actionOptions}
            value={rule.prohibited_actions ?? []}
            onChange={(v) => set("prohibited_actions", v)}
            tone="bad"
          />
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Policy references" hint="Document#section, e.g. DEL-POL-04#5.2">
          <Input value={policyRefs} onChange={(e) => setPolicyRefs(e.target.value)} />
        </Field>
        <Field label="Follow-up">
          <Optional
            value={rule.follow_up_type}
            none="None"
            options={(vocab?.follow_up_types ?? []).map((t) => ({ value: t, label: t }))}
            onChange={(v) => set("follow_up_type", v)}
          />
        </Field>
        <Field label="Follow-up within (hours)">
          <Input
            type="number"
            min={1}
            value={rule.follow_up_hours ?? ""}
            onChange={(e) => set("follow_up_hours", e.target.value ? Number(e.target.value) : null)}
          />
        </Field>
      </div>

      <div className="flex items-center gap-2">
        <Switch
          id="rule-active"
          checked={rule.is_active ?? true}
          onCheckedChange={(v) => set("is_active", v)}
        />
        <Label htmlFor="rule-active">Active</Label>
        {editing ? (
          <Badge variant="outline" className="ml-2">
            Saving creates a new version
          </Badge>
        ) : null}
      </div>

      {error ? (
        <p
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/5 p-2 text-sm text-destructive"
        >
          {error}
        </p>
      ) : null}
      <DialogFooter>
        <Button variant="outline" onClick={onDone} disabled={pending}>
          Cancel
        </Button>
        <Button
          onClick={save}
          disabled={pending || !rule.rule_id.trim() || rule.description.length < 3}
        >
          {pending ? "Saving…" : editing ? "Save changes" : "Create rule"}
        </Button>
      </DialogFooter>
    </div>
  );
}
