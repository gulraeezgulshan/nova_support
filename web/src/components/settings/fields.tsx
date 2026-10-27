"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// Form rows shared by the Settings tabs.

export function Field({
  label,
  help,
  defaultText,
  onReset,
  children,
}: {
  label: string;
  help?: string;
  /** Shown as "Default: …" with a Reset link when given. */
  defaultText?: string;
  onReset?: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-1.5 sm:grid-cols-[16rem_1fr] sm:items-start sm:gap-6">
      <div>
        <Label>{label}</Label>
        {help ? <p className="mt-1 text-xs text-muted-foreground">{help}</p> : null}
        {defaultText !== undefined ? (
          <p className="mt-1 text-xs text-muted-foreground">
            Default: {defaultText}
            {onReset ? (
              <>
                {" · "}
                <button type="button" className="underline hover:text-foreground" onClick={onReset}>
                  Reset
                </button>
              </>
            ) : null}
          </p>
        ) : null}
      </div>
      <div className="max-w-md">{children}</div>
    </div>
  );
}

export function NumberInput({
  value,
  min,
  max,
  step,
  onChange,
}: {
  value: number;
  min: number;
  max: number;
  /** Set for decimals, e.g. 0.01. */
  step?: number;
  onChange: (v: number) => void;
}) {
  return (
    <Input
      type="number"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
    />
  );
}
