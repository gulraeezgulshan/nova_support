"use client";

import { Field, NumberInput } from "@/components/settings/fields";
import type { IntakeSettings } from "@/lib/api/generated/types.gen";

type Key = keyof IntakeSettings;
type Row = { key: Key; label: string; help: string; min: number; max: number; step?: number };

const SECTIONS: { title: string; rows: Row[] }[] = [
  {
    title: "Duplicates",
    rows: [
      {
        key: "near_duplicate_min_ratio",
        label: "Near-duplicate match (%)",
        help: "70 to 100. Almost the same wording from the same customer is linked, not filed twice.",
        min: 70,
        max: 100,
      },
      {
        key: "related_min_similarity",
        label: "Related-complaint similarity",
        help: "0.50 to 0.99. The same issue in other words is linked to the earlier complaint.",
        min: 0.5,
        max: 0.99,
        step: 0.01,
      },
      {
        key: "duplicate_window_days",
        label: "Duplicate window (days)",
        help: "1 to 365. Only complaints this recent are compared.",
        min: 1,
        max: 365,
      },
    ],
  },
  {
    title: "Repeat complaints",
    rows: [
      {
        key: "repeat_window_days",
        label: "Repeat window (days)",
        help: "1 to 365. Earlier complaints this recent count as repeats.",
        min: 1,
        max: 365,
      },
      {
        key: "repeat_min_gap_hours",
        label: "Minimum gap (hours)",
        help: "0 to 168. A resend within this gap is a duplicate, not a repeat.",
        min: 0,
        max: 168,
      },
    ],
  },
  {
    title: "Complaint length",
    rows: [
      {
        key: "min_title_chars",
        label: "Title at least (characters)",
        help: "3 to 20.",
        min: 3,
        max: 20,
      },
      {
        key: "min_description_chars",
        label: "Description at least (characters)",
        help: "10 to 200.",
        min: 10,
        max: 200,
      },
      {
        key: "min_description_words",
        label: "Description at least (words)",
        help: "1 to 30.",
        min: 1,
        max: 30,
      },
      {
        key: "max_description_chars",
        label: "Description at most (characters)",
        help: "500 to 5,000; the contact form never accepts more than 5,000.",
        min: 500,
        max: 5000,
      },
    ],
  },
  {
    title: "Attachments",
    rows: [
      { key: "max_attachments", label: "Files per complaint", help: "0 to 10.", min: 0, max: 10 },
      { key: "max_attachment_mb", label: "File size (MB)", help: "1 to 10.", min: 1, max: 10 },
    ],
  },
  {
    title: "Chat",
    rows: [
      {
        key: "chat_max_questions",
        label: "Questions before the summary",
        help: "2 to 12.",
        min: 2,
        max: 12,
      },
      {
        key: "chat_max_message_chars",
        label: "Characters per message",
        help: "200 to 2,000; the chat box never accepts more than 2,000.",
        min: 200,
        max: 2000,
      },
      {
        key: "chat_max_customer_messages",
        label: "Customer messages per chat",
        help: "5 to 100.",
        min: 5,
        max: 100,
      },
    ],
  },
  {
    title: "Bulk import",
    rows: [
      { key: "import_max_rows", label: "Rows per file", help: "10 to 5,000.", min: 10, max: 5000 },
    ],
  },
];

export function IntakeSettingsForm({
  value,
  defaults,
  onChange,
}: {
  value: IntakeSettings;
  defaults: IntakeSettings;
  onChange: (patch: Partial<IntakeSettings>) => void;
}) {
  return (
    <div className="space-y-8">
      {SECTIONS.map((section) => (
        <section
          key={section.title}
          className="space-y-5 border-t pt-5 first:border-t-0 first:pt-0"
        >
          <h3 className="text-sm font-semibold">{section.title}</h3>
          {section.rows.map((r) => (
            <Field
              key={r.key}
              label={r.label}
              help={r.help}
              defaultText={String(defaults[r.key])}
              onReset={() => onChange({ [r.key]: defaults[r.key] })}
            >
              <NumberInput
                value={value[r.key]}
                min={r.min}
                max={r.max}
                step={r.step}
                onChange={(v) => onChange({ [r.key]: v })}
              />
            </Field>
          ))}
        </section>
      ))}
    </div>
  );
}
