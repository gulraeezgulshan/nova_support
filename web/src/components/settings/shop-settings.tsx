"use client";

import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";

import { Field, NumberInput } from "@/components/settings/fields";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { FaqEntrySetting, ShopSettings, SocialLink } from "@/lib/api/generated/types.gen";

/** The answer as customers will read it; unknown placeholders stay as typed. */
function preview(answer: string, values: Record<string, number>): string {
  return answer.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in values ? String(values[name]) : whole,
  );
}

function move<T>(items: T[], from: number, to: number): T[] {
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

export function ShopSettingsForm({
  value,
  defaults,
  onChange,
  policyValues,
}: {
  value: ShopSettings;
  defaults: ShopSettings;
  onChange: (patch: Partial<ShopSettings>) => void;
  policyValues: Record<string, number>;
}) {
  const setSocial = (i: number, patch: Partial<SocialLink>) =>
    onChange({ socials: value.socials.map((s, j) => (j === i ? { ...s, ...patch } : s)) });
  const setFaq = (i: number, patch: Partial<FaqEntrySetting>) =>
    onChange({ faq: value.faq.map((f, j) => (j === i ? { ...f, ...patch } : f)) });
  return (
    <div className="space-y-8">
      <Field
        label="Best-seller window (days)"
        help="7 to 365. 'Best selling' counts orders this recent."
        defaultText={String(defaults.best_seller_days)}
        onReset={() => onChange({ best_seller_days: defaults.best_seller_days })}
      >
        <NumberInput
          value={value.best_seller_days}
          min={7}
          max={365}
          onChange={(best_seller_days) => onChange({ best_seller_days })}
        />
      </Field>

      <Field
        label="Social links"
        help="Up to 8, shown in the shop footer. Links must start with https://."
        defaultText={defaults.socials.map((s) => s.name).join(", ") || "none"}
        onReset={() => onChange({ socials: defaults.socials })}
      >
        <div className="space-y-2">
          {value.socials.map((s, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2">
              <Input
                aria-label={`Social ${i + 1} name`}
                className="w-32"
                value={s.name}
                maxLength={30}
                onChange={(e) => setSocial(i, { name: e.target.value })}
              />
              <Input
                aria-label={`Social ${i + 1} link`}
                className="min-w-0 flex-1 basis-48"
                value={s.url}
                maxLength={200}
                placeholder="https://"
                onChange={(e) => setSocial(i, { url: e.target.value })}
              />
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Remove social ${i + 1}`}
                onClick={() => onChange({ socials: value.socials.filter((_, j) => j !== i) })}
              >
                <Trash2 />
              </Button>
            </div>
          ))}
          <Button
            variant="outline"
            size="sm"
            disabled={value.socials.length >= 8}
            onClick={() => onChange({ socials: [...value.socials, { name: "", url: "https://" }] })}
          >
            <Plus /> Add link
          </Button>
        </div>
      </Field>

      <section className="space-y-3 border-t pt-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-sm font-semibold">FAQ</h3>
          <p className="text-xs text-muted-foreground">
            Default: {defaults.faq.length} questions ·{" "}
            <button
              type="button"
              className="underline hover:text-foreground"
              onClick={() => onChange({ faq: defaults.faq })}
            >
              Reset
            </button>
          </p>
        </div>
        <p className="text-xs text-muted-foreground">
          Shown on the Help page and used by the chat assistant. Answers can use these policy
          numbers, filled in from the policy documents:{" "}
          {Object.entries(policyValues).map(([name, v], i) => (
            <span key={name}>
              {i ? ", " : ""}
              <code className="font-mono">{`{${name}}`}</code> = {v}
            </span>
          ))}
          .
        </p>
        {value.faq.map((item, i) => (
          <div key={i} className="space-y-2 rounded-lg border p-3">
            <div className="flex items-center gap-2">
              <Input
                aria-label={`Question ${i + 1}`}
                className="min-w-0 flex-1"
                value={item.question}
                maxLength={200}
                onChange={(e) => setFaq(i, { question: e.target.value })}
              />
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Move question ${i + 1} up`}
                disabled={i === 0}
                onClick={() => onChange({ faq: move(value.faq, i, i - 1) })}
              >
                <ArrowUp />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Move question ${i + 1} down`}
                disabled={i === value.faq.length - 1}
                onClick={() => onChange({ faq: move(value.faq, i, i + 1) })}
              >
                <ArrowDown />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Remove question ${i + 1}`}
                disabled={value.faq.length <= 1}
                onClick={() => onChange({ faq: value.faq.filter((_, j) => j !== i) })}
              >
                <Trash2 />
              </Button>
            </div>
            <Textarea
              aria-label={`Answer ${i + 1}`}
              rows={3}
              maxLength={1000}
              value={item.answer}
              onChange={(e) => setFaq(i, { answer: e.target.value })}
            />
            <p className="text-xs text-muted-foreground">
              Customers read: {preview(item.answer, policyValues)}
            </p>
          </div>
        ))}
        <Button
          variant="outline"
          size="sm"
          disabled={value.faq.length >= 20}
          onClick={() => onChange({ faq: [...value.faq, { question: "", answer: "" }] })}
        >
          <Plus /> Add question
        </Button>
      </section>
    </div>
  );
}
