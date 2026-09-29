"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { LogoUpload } from "@/components/settings/logo-upload";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  readSettingsOptions,
  readSettingsQueryKey,
  updateSettingsMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { SettingsOut, SettingsUpdate } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";

type Form = Omit<SettingsUpdate, "version">;
const EFFORTS = ["none", "minimal", "low", "medium", "high", "xhigh", "max"] as const;

function toForm(s: SettingsOut): Form {
  const { shop_name, shop_tagline, console_name, support_email, phone, address, hours } =
    s.settings.branding;
  return {
    email: s.settings.email,
    ai: s.settings.ai,
    operations: s.settings.operations,
    orders: s.settings.orders,
    branding: { shop_name, shop_tagline, console_name, support_email, phone, address, hours },
  };
}

function Field({
  label,
  help,
  children,
}: {
  label: string;
  help?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-1.5 sm:grid-cols-[16rem_1fr] sm:items-start sm:gap-6">
      <div>
        <Label>{label}</Label>
        {help ? <p className="mt-1 text-xs text-muted-foreground">{help}</p> : null}
      </div>
      <div className="max-w-md">{children}</div>
    </div>
  );
}

function NumberInput({
  value,
  min,
  max,
  onChange,
}: {
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
}) {
  return (
    <Input
      type="number"
      min={min}
      max={max}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
    />
  );
}

export function SettingsManager() {
  const queryClient = useQueryClient();
  const settings = useQuery(readSettingsOptions());
  // Only unsaved edits live in state; otherwise the form shows the saved settings.
  const [edits, setEdits] = useState<Form | null>(null);
  const save = useMutation({
    ...updateSettingsMutation(),
    onSuccess: (data) => {
      toast.success("Settings saved. They apply within about 15 seconds.");
      queryClient.setQueryData(readSettingsQueryKey(), data);
      setEdits(null);
    },
    onError: (err) => toast.error(apiErrorMessage(err, "Settings were not saved.")),
  });

  if (settings.isPending) return <Skeleton className="h-96 w-full" />;
  if (settings.isError)
    return <p className="text-sm text-destructive">{apiErrorMessage(settings.error)}</p>;
  const data = settings.data;
  const saved = toForm(data);
  const form = edits ?? saved;
  const dirty = edits !== null && JSON.stringify(edits) !== JSON.stringify(saved);
  const set = <G extends keyof Form>(group: G, patch: Partial<Form[G]>) =>
    setEdits({ ...form, [group]: { ...form[group], ...patch } });
  const models = data.suggested_models[form.ai.provider] ?? [];

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
          onClick={() => save.mutate({ body: { version: data.version, ...form } })}
        >
          Save changes
        </Button>
      </div>
    </div>
  );

  return (
    <Tabs defaultValue="email" className="space-y-6">
      <TabsList className="flex-wrap">
        <TabsTrigger value="email">E-mail & timing</TabsTrigger>
        <TabsTrigger value="ai">AI</TabsTrigger>
        <TabsTrigger value="operations">Operations</TabsTrigger>
        <TabsTrigger value="branding">Branding</TabsTrigger>
        <TabsTrigger value="policy">Policy facts</TabsTrigger>
      </TabsList>

      <TabsContent value="email" className="space-y-6 rounded-xl border p-6">
        <Field
          label="Check the mailbox every (seconds)"
          help="60 to 3600. New e-mails become complaints on this schedule."
        >
          <NumberInput
            value={form.email.mailbox_check_seconds}
            min={60}
            max={3600}
            onChange={(v) => set("email", { mailbox_check_seconds: v })}
          />
        </Field>
        <Field label="Send queued e-mails every (seconds)" help="15 to 600.">
          <NumberInput
            value={form.email.outbox_flush_seconds}
            min={15}
            max={600}
            onChange={(v) => set("email", { outbox_flush_seconds: v })}
          />
        </Field>
        <Field label="Sender name" help="Shown as the From name on every e-mail.">
          <Input
            value={form.email.from_name}
            maxLength={80}
            onChange={(e) => set("email", { from_name: e.target.value })}
          />
        </Field>
        <Field
          label="Send automatic replies"
          help="Off: verified replies also wait for a reviewer to approve them (e-mail and chat)."
        >
          <Switch
            checked={form.email.auto_replies}
            onCheckedChange={(v) => set("email", { auto_replies: v })}
          />
        </Field>
        {footer}
      </TabsContent>

      <TabsContent value="ai" className="space-y-6 rounded-xl border p-6">
        <Field label="Provider" help="Only providers with an API key on the server can be chosen.">
          <Select
            value={form.ai.provider}
            onValueChange={(v) =>
              set("ai", {
                provider: v as Form["ai"]["provider"],
                model: data.suggested_models[v]?.[0] ?? "",
              })
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(["openai", "anthropic"] as const).map((p) => (
                <SelectItem key={p} value={p} disabled={!data.providers_available.includes(p)}>
                  {p === "openai" ? "OpenAI" : "Anthropic"}
                  {data.providers_available.includes(p) ? "" : " (no API key)"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="Model" help="Pick a suggestion or type another model name for this provider.">
          <Input
            list="model-suggestions"
            value={form.ai.model}
            maxLength={100}
            onChange={(e) => set("ai", { model: e.target.value })}
          />
          <datalist id="model-suggestions">
            {models.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </Field>
        <Field
          label="Reasoning effort"
          help="Lower is faster and cheaper; higher can be more careful."
        >
          <Select
            value={form.ai.effort}
            onValueChange={(v) => set("ai", { effort: v as Form["ai"]["effort"] })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {EFFORTS.map((e) => (
                <SelectItem key={e} value={e}>
                  {e}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field
          label="Policy passages to read"
          help="3 to 20 passages retrieved from the knowledge base per complaint."
        >
          <NumberInput
            value={form.ai.retrieval_limit}
            min={3}
            max={20}
            onChange={(v) => set("ai", { retrieval_limit: v })}
          />
        </Field>
        <Field
          label="Analyse new complaints automatically"
          help="Off: staff start the analysis with Re-run analysis."
        >
          <Switch
            checked={form.ai.auto_analysis}
            onCheckedChange={(v) => set("ai", { auto_analysis: v })}
          />
        </Field>
        {footer}
      </TabsContent>

      <TabsContent value="operations" className="space-y-6 rounded-xl border p-6">
        <Field label="SLA risk scan every (minutes)" help="1 to 60.">
          <NumberInput
            value={form.operations.sla_scan_minutes}
            min={1}
            max={60}
            onChange={(v) => set("operations", { sla_scan_minutes: v })}
          />
        </Field>
        <Field
          label="Minimum score for 'verified'"
          help="50 to 100. Below it, a complaint goes to manual review."
        >
          <NumberInput
            value={form.operations.verified_min_score}
            min={50}
            max={100}
            onChange={(v) => set("operations", { verified_min_score: v })}
          />
        </Field>
        <Field
          label="Always review from escalation level"
          help="1 to 5. Complaints at or above it always get a human review."
        >
          <NumberInput
            value={form.operations.always_review_escalation_level}
            min={1}
            max={5}
            onChange={(v) => set("operations", { always_review_escalation_level: v })}
          />
        </Field>
        {footer}
      </TabsContent>

      <TabsContent value="branding" className="space-y-6 rounded-xl border p-6">
        <div className="grid gap-3 lg:grid-cols-2">
          <LogoUpload target="shop" label="Shop" url={data.shop_logo_url} />
          <LogoUpload target="console" label="Console" url={data.console_logo_url} />
        </div>
        <Field label="Shop name">
          <Input
            value={form.branding.shop_name}
            maxLength={60}
            onChange={(e) => set("branding", { shop_name: e.target.value })}
          />
        </Field>
        <Field label="Shop tagline">
          <Input
            value={form.branding.shop_tagline}
            maxLength={140}
            onChange={(e) => set("branding", { shop_tagline: e.target.value })}
          />
        </Field>
        <Field label="Console name">
          <Input
            value={form.branding.console_name}
            maxLength={40}
            onChange={(e) => set("branding", { console_name: e.target.value })}
          />
        </Field>
        <Field label="Support e-mail">
          <Input
            type="email"
            value={form.branding.support_email}
            maxLength={120}
            onChange={(e) => set("branding", { support_email: e.target.value })}
          />
        </Field>
        <Field label="Phone">
          <Input
            value={form.branding.phone}
            maxLength={40}
            onChange={(e) => set("branding", { phone: e.target.value })}
          />
        </Field>
        <Field label="Address">
          <Input
            value={form.branding.address}
            maxLength={200}
            onChange={(e) => set("branding", { address: e.target.value })}
          />
        </Field>
        <Field label="Opening hours">
          <Input
            value={form.branding.hours}
            maxLength={100}
            onChange={(e) => set("branding", { hours: e.target.value })}
          />
        </Field>
        {footer}
      </TabsContent>

      <TabsContent value="policy" className="space-y-4 rounded-xl border p-6">
        <p className="text-sm text-muted-foreground">
          These come from the policy documents, so the shop, the AI and the rules always agree. To
          change one, upload a new version of the document in the Knowledge base.
        </p>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fact</TableHead>
              <TableHead>Value</TableHead>
              <TableHead>Source</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.policy_facts.map((f) => (
              <TableRow key={f.fact}>
                <TableCell>{f.fact}</TableCell>
                <TableCell className="font-medium">{f.value}</TableCell>
                <TableCell className="font-mono text-xs">
                  {f.source}
                  {f.version ? ` v${f.version}` : " (not active)"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TabsContent>
    </Tabs>
  );
}
