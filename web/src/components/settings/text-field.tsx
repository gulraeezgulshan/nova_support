"use client";

import { useRef } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { PlaceholderRule } from "@/lib/api/generated/types.gen";

const FIELD = /\{([^{}]*)\}/g;

/** The text as a customer reads it: allowed placeholders filled, anything else left as typed. */
export function fill(text: string, allowed: string[], samples: Record<string, string>): string {
  return text.replace(FIELD, (whole, name: string) =>
    allowed.includes(name) && name in samples ? samples[name] : whole,
  );
}

function problems(text: string, rule: PlaceholderRule): string[] {
  const found = [...text.matchAll(FIELD)].map((m) => m[1]);
  const unknown = [...new Set(found.filter((n) => !rule.allowed.includes(n)))];
  return [
    ...unknown.map((n) => `Unknown placeholder {${n}}`),
    ...rule.required.filter((n) => !found.includes(n)).map((n) => `Must include {${n}}`),
  ];
}

/** One customer text: placeholder buttons, Default · Reset, and a live preview. */
export function TextField({
  label,
  value,
  defaultValue,
  rule,
  samples,
  multiline = false,
  suffix = "",
  onChange,
}: {
  label: string;
  value: string;
  defaultValue: string;
  rule: PlaceholderRule;
  samples: Record<string, string>;
  multiline?: boolean;
  /** Appended to the preview only (e.g. the e-mail signature). */
  suffix?: string;
  onChange: (next: string) => void;
}) {
  const ref = useRef<HTMLInputElement & HTMLTextAreaElement>(null);
  const insert = (name: string) => {
    const el = ref.current;
    const token = `{${name}}`;
    const start = el?.selectionStart ?? value.length;
    const end = el?.selectionEnd ?? value.length;
    onChange(value.slice(0, start) + token + value.slice(end));
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(start + token.length, start + token.length);
    });
  };
  const issues = problems(value, rule);
  const Control = multiline ? Textarea : Input;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Label>{label}</Label>
        <p className="text-xs text-muted-foreground">
          Default ·{" "}
          <button
            type="button"
            className="underline hover:text-foreground"
            disabled={value === defaultValue}
            onClick={() => onChange(defaultValue)}
          >
            Reset
          </button>
        </p>
      </div>
      <Control
        ref={ref}
        aria-label={label}
        value={value}
        rows={multiline ? 5 : undefined}
        onChange={(e) => onChange(e.target.value)}
      />
      {rule.allowed.length ? (
        <div className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
          Insert:
          {rule.allowed.map((name) => (
            <button
              key={name}
              type="button"
              className="rounded border px-1.5 py-0.5 font-mono hover:bg-muted"
              onClick={() => insert(name)}
            >
              {`{${name}}`}
            </button>
          ))}
        </div>
      ) : null}
      {issues.map((issue) => (
        <p key={issue} className="text-xs text-destructive">
          {issue}
        </p>
      ))}
      <div className="rounded-md bg-muted/50 p-2 text-xs whitespace-pre-wrap text-muted-foreground">
        {fill(value, rule.allowed, samples) + suffix}
      </div>
    </div>
  );
}
