"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  checkPatternsOnDatasetMutation,
  testPatternsMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type {
  DatasetCheckOut,
  PatternSettings,
  TextSide,
} from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

function Change({ saved, draft, total }: { saved: number; draft: number; total?: number }) {
  return (
    <span className={cn("font-mono", saved !== draft && "font-semibold text-primary")}>
      {saved} → {draft}
      {total !== undefined ? ` / ${total}` : ""}
    </span>
  );
}

function Side({ title, side, other }: { title: string; side: TextSide; other: TextSide }) {
  const c = side.classification;
  return (
    <div className="space-y-2 rounded-md border p-2 text-xs">
      <p className="font-medium">{title}</p>
      <div className="flex flex-wrap gap-1">
        {Object.entries(side.signals).length ? (
          Object.entries(side.signals).flatMap(([signal, phrases]) =>
            phrases.map((phrase) => (
              <Badge
                key={`${signal}:${phrase}`}
                variant={other.signals[signal]?.includes(phrase) ? "secondary" : "default"}
                className="font-mono"
              >
                {signal}: {phrase}
              </Badge>
            )),
          )
        ) : (
          <span className="text-muted-foreground">No signals</span>
        )}
      </div>
      <p>
        Classifier: <span className="font-medium">{c.status}</span>
        {c.primary ? <span className="font-mono"> {c.primary}</span> : null}
      </p>
      {c.candidates.length ? (
        <p className="text-muted-foreground">
          {c.candidates.map((k) => `${k.category}/${k.subcategory} ${k.score}`).join(" · ")}
        </p>
      ) : null}
      {side.sentences
        .filter((s) => s.commitment || s.kinds.length)
        .map((s, i) => (
          <p key={i} className="text-muted-foreground">
            “{s.sentence}” —{" "}
            {s.commitment ? (s.conditional ? "conditional" : "promise") : "no commitment"}
            {s.kinds.length ? `: ${s.kinds.join(", ")}` : ""}
          </p>
        ))}
    </div>
  );
}

function DatasetResult({ r }: { r: DatasetCheckOut }) {
  const changed = r.signals.filter((s) => s.saved !== s.draft);
  return (
    <div className="space-y-3 text-xs">
      <table className="w-full">
        <tbody>
          <tr>
            <td className="py-0.5">Category right</td>
            <td className="text-right">
              <Change
                saved={r.classifier.saved_correct}
                draft={r.classifier.draft_correct}
                total={r.total}
              />
            </td>
          </tr>
          <tr>
            <td className="py-0.5">Confident</td>
            <td className="text-right">
              <Change saved={r.classifier.saved_confident} draft={r.classifier.draft_confident} />
            </td>
          </tr>
          <tr>
            <td className="py-0.5">Escalation matches label</td>
            <td className="text-right">
              <Change {...r.escalation} />
            </td>
          </tr>
          <tr>
            <td className="py-0.5">Urgency matches label</td>
            <td className="text-right">
              <Change {...r.urgency} />
            </td>
          </tr>
          <tr>
            <td className="py-0.5">Injection found (false alarms)</td>
            <td className="text-right font-mono">
              {r.prompt_injection.saved.true_positive} ({r.prompt_injection.saved.false_positive})
              → {r.prompt_injection.draft.true_positive} (
              {r.prompt_injection.draft.false_positive})
            </td>
          </tr>
        </tbody>
      </table>
      {r.classifier.right_to_wrong.length ? (
        <p>Now wrong: {r.classifier.right_to_wrong.join(", ")}</p>
      ) : null}
      {r.classifier.wrong_to_right.length ? (
        <p>Now right: {r.classifier.wrong_to_right.join(", ")}</p>
      ) : null}
      <div>
        <p className="font-medium">Signals (complaints that fire)</p>
        {changed.length ? (
          changed.map((s) => (
            <div key={s.signal} className="mt-1">
              <p className="font-mono">
                {s.signal} <Change saved={s.saved} draft={s.draft} />
              </p>
              {[...s.gained.map((h) => ["+", h] as const), ...s.lost.map((h) => ["−", h] as const)].map(
                ([sign, h]) => (
                  <p key={sign + h.dataset_id} className="text-muted-foreground">
                    {sign} {h.dataset_id}: {h.phrases.join(", ")}
                  </p>
                ),
              )}
            </div>
          ))
        ) : (
          <p className="text-muted-foreground">No signal changes.</p>
        )}
      </div>
    </div>
  );
}

/** Try the unsaved draft on a pasted text and on the labelled sample complaints. */
export function PatternTestPanel({ draft }: { draft: PatternSettings }) {
  const [text, setText] = useState("");
  const textTest = useMutation({
    ...testPatternsMutation(),
    onError: (err) => toast.error(apiErrorMessage(err, "The test did not run.")),
  });
  const dataset = useMutation({
    ...checkPatternsOnDatasetMutation(),
    onError: (err) => toast.error(apiErrorMessage(err, "The dataset check did not run.")),
  });
  return (
    <aside className="space-y-6 rounded-xl border p-4">
      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Try a text</h3>
        <Textarea
          aria-label="Text to test"
          rows={5}
          maxLength={5000}
          value={text}
          placeholder="Paste a complaint or a reply…"
          onChange={(e) => setText(e.target.value)}
        />
        <Button
          size="sm"
          disabled={!text.trim() || textTest.isPending}
          onClick={() => textTest.mutate({ body: { draft, text } })}
        >
          Test
        </Button>
        {textTest.data ? (
          <div className="space-y-2">
            <Side title="Saved" side={textTest.data.saved} other={textTest.data.draft} />
            <Side title="Your draft" side={textTest.data.draft} other={textTest.data.saved} />
          </div>
        ) : null}
      </section>
      <section className="space-y-2 border-t pt-4">
        <h3 className="text-sm font-semibold">Check against 536 labelled complaints</h3>
        <p className="text-xs text-muted-foreground">Saved → your draft. Saving is allowed either way.</p>
        <Button
          size="sm"
          variant="outline"
          disabled={dataset.isPending}
          onClick={() => dataset.mutate({ body: { draft } })}
        >
          {dataset.isPending ? "Checking…" : "Run dataset check"}
        </Button>
        {dataset.data ? <DatasetResult r={dataset.data} /> : null}
      </section>
    </aside>
  );
}
