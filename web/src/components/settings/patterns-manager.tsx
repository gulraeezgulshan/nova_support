"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/settings/fields";
import { PatternList } from "@/components/settings/pattern-list";
import { PatternTestPanel } from "@/components/settings/pattern-test-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  listCategoriesOptions,
  readPatternsOptions,
  readPatternsQueryKey,
  recomputeSignalsMutation,
  updatePatternsMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { PatternSettings, PromisePatterns } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";

const KIND_LABELS: Record<string, string> = {
  refund: "Refund",
  replacement: "Replacement",
  compensation: "Compensation",
  policy_exception: "Policy exception",
};

function Card({ title, help, children }: { title: string; help?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3 rounded-lg border p-4">
      <div>
        <h3 className="font-mono text-sm font-semibold">{title}</h3>
        {help ? <p className="mt-0.5 text-xs text-muted-foreground">{help}</p> : null}
      </div>
      {children}
    </section>
  );
}

export function PatternsManager() {
  const queryClient = useQueryClient();
  const query = useQuery(readPatternsOptions());
  const categories = useQuery(listCategoriesOptions());
  const [edits, setEdits] = useState<PatternSettings | null>(null);
  const [category, setCategory] = useState("");
  const [subcategory, setSubcategory] = useState("");
  const save = useMutation({
    ...updatePatternsMutation(),
    onSuccess: (data) => {
      toast.success("Patterns saved. They apply within about 15 seconds.");
      queryClient.setQueryData(readPatternsQueryKey(), data);
      setEdits(null);
    },
    onError: (err) => toast.error(apiErrorMessage(err, "Patterns were not saved.")),
  });
  const recompute = useMutation({
    ...recomputeSignalsMutation(),
    onSuccess: () =>
      toast.success("Recomputing signals in the background. Reload later to see the result."),
    onError: (err) => toast.error(apiErrorMessage(err, "Recompute did not start.")),
  });

  if (query.isPending) return <Skeleton className="h-96 w-full" />;
  if (query.isError)
    return <p className="text-sm text-destructive">{apiErrorMessage(query.error)}</p>;
  const data = query.data;
  const form = edits ?? data.patterns;
  const dirty = edits !== null && JSON.stringify(edits) !== JSON.stringify(data.patterns);
  const setPromises = (patch: Partial<PromisePatterns>) =>
    setEdits({ ...form, promises: { ...form.promises, ...patch } });

  const cats = categories.data ?? [];
  const cat = category || cats[0]?.code || "";
  const subs = cats.find((c) => c.code === cat)?.subcategories ?? [];
  const sub = subs.some((s) => s.code === subcategory) ? subcategory : (subs[0]?.code ?? "");
  const phrases = form.classifier[cat]?.[sub] ?? [];
  const last = data.last_recompute;

  const footer = (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
      <p className="text-xs text-muted-foreground">
        {data.updated_at
          ? `Last changed by ${data.updated_by ?? "an administrator"} on ${new Date(data.updated_at).toLocaleString()}`
          : "Using the default settings."}
      </p>
      <div className="flex gap-2">
        <Button variant="ghost" disabled={!dirty} onClick={() => setEdits(null)}>
          Discard
        </Button>
        <Button
          disabled={!dirty || save.isPending}
          onClick={() => save.mutate({ body: { version: data.version, patterns: form } })}
        >
          {save.isPending ? "Checking…" : "Save changes"}
        </Button>
      </div>
    </div>
  );

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[1fr_24rem]">
      <Tabs defaultValue="signals" className="min-w-0 space-y-6">
        <TabsList className="flex-wrap">
          <TabsTrigger value="signals">Risk signals</TabsTrigger>
          <TabsTrigger value="classifier">Classifier</TabsTrigger>
          <TabsTrigger value="promises">Promises</TabsTrigger>
        </TabsList>

        <TabsContent value="signals" className="space-y-4">
          <div className="flex flex-wrap items-center gap-3 rounded-lg border p-4 text-xs">
            <p className="flex-1 text-muted-foreground">
              New analyses use saved changes at once. Stored complaints keep their signals until you
              recompute them.
              {last
                ? ` Last run: ${new Date(last.at).toLocaleString()}, ${last.changed} of ${last.total} complaints changed.`
                : ""}
            </p>
            <Button
              size="sm"
              variant="outline"
              disabled={recompute.isPending}
              onClick={() => recompute.mutate({})}
            >
              Recompute signals
            </Button>
          </div>
          {Object.entries(form.signals).map(([name, entries]) => (
            <Card key={name} title={name} help={data.signal_descriptions[name]}>
              <PatternList
                entries={entries}
                defaults={data.defaults.signals[name] ?? []}
                onChange={(next) => setEdits({ ...form, signals: { ...form.signals, [name]: next } })}
              />
            </Card>
          ))}
          {footer}
        </TabsContent>

        <TabsContent value="classifier" className="space-y-4">
          <div className="grid gap-2 sm:grid-cols-2">
            <Select value={cat} onValueChange={setCategory}>
              <SelectTrigger aria-label="Category" className="w-full">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                {cats.map((c) => (
                  <SelectItem key={c.code} value={c.code}>
                    {c.code}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={sub} onValueChange={setSubcategory}>
              <SelectTrigger aria-label="Subcategory" className="w-full">
                <SelectValue placeholder="Subcategory" />
              </SelectTrigger>
              <SelectContent>
                {subs.map((s) => (
                  <SelectItem key={s.code} value={s.code}>
                    {s.code}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {sub ? (
            <Card
              title={`${cat}/${sub}`}
              help={
                phrases.length
                  ? "Weight: 3 decisive phrase, 2 strong hint, 1 weak hint."
                  : "No phrases: Python never names it."
              }
            >
              <PatternList
                entries={phrases}
                defaults={data.defaults.classifier[cat]?.[sub] ?? []}
                weighted
                onChange={(next) =>
                  setEdits({
                    ...form,
                    classifier: {
                      ...form.classifier,
                      [cat]: { ...form.classifier[cat], [sub]: next },
                    },
                  })
                }
              />
            </Card>
          ) : null}
          {footer}
        </TabsContent>

        <TabsContent value="promises" className="space-y-4">
          <Card
            title="Commitment"
            help="A reply sentence is a commitment when it says something will happen."
          >
            <PatternList
              entries={form.promises.commitment}
              defaults={data.defaults.promises.commitment}
              onChange={(commitment) => setPromises({ commitment })}
            />
          </Card>
          <Card title="Conditional" help="Wording that makes a commitment conditional (not a promise).">
            <PatternList
              entries={form.promises.conditional}
              defaults={data.defaults.promises.conditional}
              onChange={(conditional) => setPromises({ conditional })}
            />
          </Card>
          {Object.entries(form.promises.kinds).map(([kind, entries]) => (
            <Card key={kind} title={KIND_LABELS[kind] ?? kind}>
              <div className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                Allowed when the rules require:
                {(data.supported_by[kind] ?? []).map((code) => (
                  <Badge key={code} variant="secondary" className="font-mono">
                    {code}
                  </Badge>
                ))}
              </div>
              <PatternList
                entries={entries}
                defaults={data.defaults.promises.kinds[kind] ?? []}
                onChange={(next) => setPromises({ kinds: { ...form.promises.kinds, [kind]: next } })}
              />
            </Card>
          ))}
          <Card title="Deadline" help="One regex with 3 groups: amount, business/working, unit.">
            <Field
              label="Regex"
              defaultText="the shipped pattern"
              onReset={() => setPromises({ deadline: data.defaults.promises.deadline })}
            >
              <Input
                aria-label="Deadline regex"
                className="font-mono text-xs"
                value={form.promises.deadline}
                maxLength={300}
                onChange={(e) => setPromises({ deadline: e.target.value })}
              />
            </Field>
          </Card>
          {footer}
        </TabsContent>
      </Tabs>
      <PatternTestPanel draft={form} />
    </div>
  );
}
