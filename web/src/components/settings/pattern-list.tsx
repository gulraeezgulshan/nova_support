"use client";

import { Plus, Trash2 } from "lucide-react";

import { NumberInput } from "@/components/settings/fields";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { PatternEntry } from "@/lib/api/generated/types.gen";

/** A phrase/regex entry; classifier entries also carry a weight (1–3). */
export type Entry = PatternEntry & { weight?: number };

/** An editable list of pattern entries with Add and "Default: N entries · Reset". */
export function PatternList<E extends Entry>({
  entries,
  defaults,
  weighted = false,
  onChange,
}: {
  entries: E[];
  defaults: E[];
  weighted?: boolean;
  onChange: (next: E[]) => void;
}) {
  const update = (index: number, patch: Partial<Entry>) =>
    onChange(entries.map((e, i) => (i === index ? { ...e, ...patch } : e)));
  return (
    <div className="space-y-2">
      {entries.map((entry, index) => (
        <div key={index} className="flex flex-wrap items-center gap-2">
          <Input
            aria-label={`Entry ${index + 1}`}
            className="min-w-0 flex-1 basis-48 font-mono text-xs"
            value={entry.text}
            maxLength={300}
            placeholder={entry.mode === "phrase" ? "words to match" : "regular expression"}
            onChange={(e) => update(index, { text: e.target.value })}
          />
          <Select
            value={entry.mode}
            onValueChange={(mode) => update(index, { mode: mode as Entry["mode"] })}
          >
            <SelectTrigger aria-label={`Entry ${index + 1} kind`} className="w-24">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="phrase">Phrase</SelectItem>
              <SelectItem value="regex">Regex</SelectItem>
            </SelectContent>
          </Select>
          {weighted ? (
            <div className="w-16" title="Weight: 3 decisive, 2 strong hint, 1 weak hint">
              <NumberInput
                value={entry.weight ?? 1}
                min={1}
                max={3}
                onChange={(weight) => update(index, { weight })}
              />
            </div>
          ) : null}
          <Button
            variant="ghost"
            size="icon"
            aria-label={`Remove entry ${index + 1}`}
            onClick={() => onChange(entries.filter((_, i) => i !== index))}
          >
            <Trash2 />
          </Button>
        </div>
      ))}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            onChange([
              ...entries,
              { text: "", mode: "phrase", ...(weighted ? { weight: 2 } : {}) } as E,
            ])
          }
        >
          <Plus /> Add
        </Button>
        <p className="text-xs text-muted-foreground">
          Default: {defaults.length} {defaults.length === 1 ? "entry" : "entries"}
          {" · "}
          <button
            type="button"
            className="underline hover:text-foreground"
            onClick={() => onChange(defaults)}
          >
            Reset
          </button>
        </p>
      </div>
    </div>
  );
}
