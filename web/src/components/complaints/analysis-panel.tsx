"use client";

import { AlertTriangle, ShieldAlert } from "lucide-react";
import { useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { AnalysisRunOut } from "@/lib/api/generated/types.gen";
import { formatDateTime, humanize } from "@/lib/format";

import { PriorityBadge } from "./badges";

export function AnalysisPanel({ run }: { run: AnalysisRunOut }) {
  const [showJson, setShowJson] = useState(false);
  const a = run.output;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle>AI analysis (Pipeline 1)</CardTitle>
            <CardDescription>
              Recommendation only. Python rule validation checks it before it can be used.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={() => setShowJson(!showJson)}>
            {showJson ? "Hide JSON" : "Show JSON"}
          </Button>
        </div>
        <RunMeta run={run} />
      </CardHeader>
      <CardContent className="space-y-5">
        {run.status !== "completed" ? (
          <Alert variant="destructive">
            <AlertTriangle />
            <AlertTitle>
              {run.status === "needs_review"
                ? "Model output failed validation; sent to manual review"
                : run.status === "failed"
                  ? "Analysis could not be completed"
                  : "Analysis in progress"}
            </AlertTitle>
            {run.validation_errors.length || run.error ? (
              <AlertDescription>
                <ul className="list-disc pl-4">
                  {run.error ? <li>{run.error}</li> : null}
                  {run.validation_errors.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              </AlertDescription>
            ) : null}
          </Alert>
        ) : null}

        {showJson ? (
          <pre className="max-h-[32rem] overflow-auto rounded-lg bg-muted p-4 text-xs">
            {JSON.stringify(a, null, 2)}
          </pre>
        ) : a ? (
          <Tabs defaultValue="summary">
            <TabsList>
              <TabsTrigger value="summary">Summary</TabsTrigger>
              <TabsTrigger value="resolution">Resolution</TabsTrigger>
              <TabsTrigger value="response">Customer response</TabsTrigger>
              <TabsTrigger value="policies">Policies ({a.policy_references.length})</TabsTrigger>
            </TabsList>

            <TabsContent value="summary" className="space-y-4 pt-3">
              <p className="text-sm">{a.complaint_summary}</p>
              <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
                <Item label="Category">
                  {humanize(a.primary_issue.category)} / {humanize(a.primary_issue.subcategory)}
                </Item>
                <Item label="Priority">
                  <PriorityBadge priority={a.priority} /> <span>{a.urgency} urgency</span>
                </Item>
                <Item label="Department">
                  {humanize(a.department)}
                  {a.supporting_departments.length
                    ? ` + ${a.supporting_departments.map(humanize).join(", ")}`
                    : ""}
                </Item>
                <Item label="Sentiment">
                  {a.sentiment}
                  {a.emotions.length ? ` (${a.emotions.join(", ")})` : ""}
                </Item>
                <Item label="Escalation">
                  {a.escalation.required ? humanize(a.escalation.level) : "Not required"}
                </Item>
                <Item label="Follow-up">
                  {a.follow_up.required
                    ? `${humanize(a.follow_up.type)} within ${a.follow_up.within_hours} h`
                    : "None"}
                </Item>
              </dl>
              <p className="text-sm text-muted-foreground">
                <span className="font-medium text-foreground">Why this urgency: </span>
                {a.urgency_rationale}
              </p>
              {a.secondary_issues.length ? (
                <Section title="Secondary issues">
                  {a.secondary_issues.map((i) => (
                    <li key={`${i.category}-${i.subcategory}`}>
                      {humanize(i.subcategory)}: {i.description}
                    </li>
                  ))}
                </Section>
              ) : null}
              {a.suspicious_instructions.length ? (
                <Alert>
                  <ShieldAlert />
                  <AlertTitle>Instructions found inside the complaint (ignored)</AlertTitle>
                  <AlertDescription>
                    <ul className="list-disc pl-4">
                      {a.suspicious_instructions.map((s) => (
                        <li key={s}>“{s}”</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              ) : null}
              {a.missing_information.length ? (
                <Section title="Missing information">
                  {a.missing_information.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </Section>
              ) : null}
              {a.clarification_questions.length ? (
                <Section title="Questions to ask the customer">
                  {a.clarification_questions.map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </Section>
              ) : null}
            </TabsContent>

            <TabsContent value="resolution" className="space-y-4 pt-3">
              <ol className="space-y-2">
                {a.resolution_steps.map((step, i) => (
                  <li key={`${step.action_code}-${i}`} className="rounded-lg border p-3 text-sm">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <Badge variant="secondary" className="font-mono text-[11px]">
                        {step.action_code}
                      </Badge>
                      {step.policy_chunk ? (
                        <code className="text-xs text-muted-foreground">{step.policy_chunk}</code>
                      ) : null}
                    </div>
                    {step.description}
                  </li>
                ))}
              </ol>
              <Section title="Agent guidance">
                {a.agent_guidance.map((g) => (
                  <li key={g}>{g}</li>
                ))}
              </Section>
              <p className="text-sm">
                <span className="font-medium">Compensation: </span>
                {a.compensation.offered
                  ? `${humanize(a.compensation.type)}${a.compensation.amount ? ` (USD ${a.compensation.amount})` : ""}`
                  : "none offered"}
              </p>
              {a.escalation.notes ? (
                <Section title="Escalation notes">
                  <li>{a.escalation.notes.summary}</li>
                  <li>Reason: {a.escalation.notes.reason}</li>
                  <li>Next action: {a.escalation.notes.required_next_action}</li>
                </Section>
              ) : null}
            </TabsContent>

            <TabsContent value="response" className="space-y-3 pt-3">
              <p className="text-sm text-muted-foreground">
                {a.customer_response.response_type} · {a.customer_response.tone} tone · draft, not
                sent
              </p>
              <div className="rounded-lg border bg-muted/40 p-4 text-sm">
                <p className="mb-2 font-medium">{a.customer_response.subject}</p>
                <p className="whitespace-pre-line">{a.customer_response.body}</p>
              </div>
              {a.follow_up.message ? (
                <p className="text-sm">
                  <span className="font-medium">Follow-up message: </span>
                  {a.follow_up.message}
                </p>
              ) : null}
            </TabsContent>

            <TabsContent value="policies" className="space-y-2 pt-3">
              {a.policy_references.map((ref) => (
                <div key={ref.chunk_code} className="rounded-lg border p-3 text-sm">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <code className="text-xs">{ref.chunk_code}</code>
                    <Badge variant="outline">{humanize(ref.applicability)}</Badge>
                  </div>
                  {ref.reason}
                </div>
              ))}
              <p className="pt-2 text-xs text-muted-foreground">
                Passages retrieved for this analysis:{" "}
                {run.retrieved_policies.map((p) => String(p.chunk_code)).join(", ") || "none"}
              </p>
            </TabsContent>
          </Tabs>
        ) : null}
      </CardContent>
    </Card>
  );
}

function RunMeta({ run }: { run: AnalysisRunOut }) {
  return (
    <p className="text-xs text-muted-foreground">
      {run.provider}/{run.model} · prompt {run.prompt_name} v{run.prompt_version} · schema{" "}
      {run.schema_version} · {run.attempts} attempt{run.attempts === 1 ? "" : "s"} ·{" "}
      {(run.latency_ms / 1000).toFixed(1)} s · {run.input_tokens + run.output_tokens} tokens ·{" "}
      {formatDateTime(run.completed_at ?? run.created_at)}
    </p>
  );
}

function Item({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="flex flex-wrap items-center gap-1">{children}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-sm font-medium">{title}</p>
      <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">{children}</ul>
    </div>
  );
}
