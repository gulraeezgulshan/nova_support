"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleSlash, RefreshCw, TriangleAlert, XCircle } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  getComplaintQueryKey,
  getValidationOptions,
  getValidationQueryKey,
  revalidateMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { CheckResultOut, ValidationRunOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { formatDateTime, humanize } from "@/lib/format";
import { cn } from "@/lib/utils";

const VERDICT_STYLES: Record<string, string> = {
  verified: "border-emerald-600/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  corrected: "border-sky-600/40 bg-sky-500/10 text-sky-700 dark:text-sky-400",
  needs_review: "border-red-600/40 bg-red-500/10 text-red-700 dark:text-red-400",
};
const VERDICT_LABELS: Record<string, string> = {
  verified: "Verified",
  corrected: "Verified with corrections",
  needs_review: "Needs review",
};

export function VerdictBadge({ verdict }: { verdict?: string | null }) {
  if (!verdict) return null;
  return (
    <Badge variant="outline" className={VERDICT_STYLES[verdict]}>
      {VERDICT_LABELS[verdict] ?? verdict}
    </Badge>
  );
}

function StatusIcon({ status }: { status: string }) {
  const common = "size-4 shrink-0";
  if (status === "pass") return <CheckCircle2 className={cn(common, "text-emerald-600")} />;
  if (status === "warn") return <TriangleAlert className={cn(common, "text-amber-600")} />;
  if (status === "fail") return <XCircle className={cn(common, "text-red-600")} />;
  return <CircleSlash className={cn(common, "text-muted-foreground")} />;
}

function display(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.join(", ") || "—";
  if (typeof value === "object") return JSON.stringify(value);
  return humanize(String(value)).replace(/^P(\d)$/, "P$1");
}

export function ValidationPanel({ complaintRef }: { complaintRef: string }) {
  const queryClient = useQueryClient();
  const validation = useQuery(getValidationOptions({ path: { ref: complaintRef } }));
  const revalidate = useMutation({
    ...revalidateMutation(),
    onSuccess: () => {
      toast.success("Validation re-run");
      queryClient.invalidateQueries({
        queryKey: getValidationQueryKey({ path: { ref: complaintRef } }),
      });
      queryClient.invalidateQueries({
        queryKey: getComplaintQueryKey({ path: { ref: complaintRef } }),
      });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  const run = validation.data;
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle>Ground-truth validation (Pipeline 2)</CardTitle>
            <CardDescription>
              Python checks against the rule matrix, active policy and traceable facts. No AI
              involved.
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => revalidate.mutate({ path: { ref: complaintRef } })}
            disabled={revalidate.isPending}
          >
            <RefreshCw /> Re-validate
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {!run ? (
          <p className="text-sm text-muted-foreground">
            {validation.isPending ? "Loading…" : "Not validated yet."}
          </p>
        ) : (
          <ValidationBody run={run} />
        )}
      </CardContent>
    </Card>
  );
}

function ValidationBody({ run }: { run: ValidationRunOut }) {
  const failing = run.checks.filter((c) => c.status === "fail");
  const hasExpected = run.comparison.some((r) => r.expected !== null && r.expected !== undefined);
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <VerdictBadge verdict={run.verdict} />
        <span className="text-sm">
          Score <span className="font-semibold tabular-nums">{run.score.toFixed(1)}</span> / 100
        </span>
        <span className="text-xs text-muted-foreground">
          {run.checks.length} checks · {failing.length} failed · rules {run.rules_version} ·{" "}
          {formatDateTime(run.created_at)}
        </span>
      </div>

      {run.review_reasons.length ? (
        <div className="rounded-lg border border-red-600/30 bg-red-500/5 p-3 text-sm">
          <p className="mb-1 font-medium">Why a human must review</p>
          <ul className="list-disc space-y-1 pl-5">
            {run.review_reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {run.corrections.length ? (
        <div className="rounded-lg border border-sky-600/30 bg-sky-500/5 p-3 text-sm">
          <p className="mb-1 font-medium">Enforced by Python</p>
          <ul className="list-disc space-y-1 pl-5">
            {run.corrections.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div>
        <p className="mb-2 text-sm font-medium">GenAI vs Python</p>
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Field</TableHead>
                <TableHead>GenAI</TableHead>
                <TableHead>Python (rules)</TableHead>
                {hasExpected ? <TableHead>Dataset label</TableHead> : null}
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {run.comparison.map((row) => (
                <TableRow key={row.field}>
                  <TableCell className="font-medium">{humanize(row.field)}</TableCell>
                  <TableCell>{display(row.genai)}</TableCell>
                  <TableCell>{display(row.python)}</TableCell>
                  {hasExpected ? <TableCell>{display(row.expected)}</TableCell> : null}
                  <TableCell>
                    {row.match ? (
                      <CheckCircle2 className="size-4 text-emerald-600" />
                    ) : (
                      <span className="text-xs text-muted-foreground" title={row.explanation}>
                        <XCircle className="inline size-4 text-red-600" /> {row.explanation}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      <div>
        <p className="mb-2 text-sm font-medium">Checks</p>
        <ul className="divide-y rounded-lg border">
          {run.checks.map((c) => (
            <CheckRow key={c.code} check={c} />
          ))}
        </ul>
      </div>
    </div>
  );
}

function CheckRow({ check }: { check: CheckResultOut }) {
  const details = [
    check.expected !== null && check.expected !== undefined
      ? `Expected: ${display(check.expected)}`
      : null,
    check.actual !== null && check.actual !== undefined ? `Actual: ${display(check.actual)}` : null,
    check.evidence?.length ? `Evidence: ${check.evidence.join("; ")}` : null,
  ].filter(Boolean);
  return (
    <li className="flex gap-3 p-3 text-sm">
      <StatusIcon status={check.status} />
      <div className="min-w-0 space-y-0.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{check.name}</span>
          <Badge variant="outline" className="text-[10px] uppercase">
            {check.severity}
          </Badge>
          {check.correctable && check.status === "fail" ? (
            <Badge variant="secondary" className="text-[10px]">
              auto-corrected
            </Badge>
          ) : null}
        </div>
        <p className="text-muted-foreground">{check.message}</p>
        {details.length && check.status !== "pass" ? (
          <p className="break-words text-xs text-muted-foreground">{details.join(" · ")}</p>
        ) : null}
      </div>
    </li>
  );
}
