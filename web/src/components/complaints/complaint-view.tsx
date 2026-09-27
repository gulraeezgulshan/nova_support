"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Flag, RefreshCw } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { DeliveryControls } from "@/components/shop/delivery-controls";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getComplaintAnalysisOptions,
  getComplaintAnalysisQueryKey,
  getComplaintOptions,
  reanalyzeComplaintMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ComplaintDetail } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { formatDate, formatDateTime, humanize } from "@/lib/format";

import { AnalysisPanel } from "./analysis-panel";
import { ChatTranscript } from "./chat-transcript";
import { ReviewPanel } from "./review-panel";
import { StatusControl } from "./status-control";
import { ValidationPanel, VerdictBadge } from "./validation-panel";
import { EscalationBadge, PriorityBadge, SlaBadge, StatusBadge } from "./badges";

const SIGNAL_LABELS: Record<string, string> = {
  safety_hazard: "Safety hazard",
  injury: "Injury",
  privacy_exposure: "Privacy exposure",
  account_compromise: "Account compromise",
  legal_threat: "Legal threat",
  repeat_contact: "Repeat contact",
  cancellation_threat: "Cancellation threat",
  emotional_intensity: "Strong emotion",
  prompt_injection: "Prompt injection",
  policy_claim: "Policy claim",
  repeated_repair: "Repeated repair",
  requests_refund: "Asks for refund",
  requests_replacement: "Asks for replacement",
  requests_compensation: "Asks for compensation",
};
const RISK_SIGNALS = new Set([
  "safety_hazard",
  "injury",
  "privacy_exposure",
  "account_compromise",
  "legal_threat",
  "prompt_injection",
]);

export function ComplaintView({
  complaintRef,
  staff,
  canReview,
  isAdmin = false,
}: {
  complaintRef: string;
  staff: boolean;
  canReview: boolean;
  isAdmin?: boolean;
}) {
  const queryClient = useQueryClient();
  const complaint = useQuery(getComplaintOptions({ path: { ref: complaintRef } }));
  const analysis = useQuery({
    ...getComplaintAnalysisOptions({ path: { ref: complaintRef } }),
    enabled: staff,
    // Poll until the background analysis has finished.
    refetchInterval: (q) => {
      const latest = q.state.data?.latest;
      return !latest || latest.status === "queued" || latest.status === "running" ? 3000 : false;
    },
  });
  const reanalyze = useMutation({
    ...reanalyzeComplaintMutation(),
    onSuccess: () => {
      toast.success("Analysis queued");
      queryClient.invalidateQueries({
        queryKey: getComplaintAnalysisQueryKey({ path: { ref: complaintRef } }),
      });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  if (complaint.isPending) return <Skeleton className="h-96 w-full" />;
  if (complaint.isError) {
    return <p className="text-sm text-destructive">{apiErrorMessage(complaint.error)}</p>;
  }
  const c = complaint.data;

  return (
    <>
      <PageHeader
        title={c.title}
        description={`${c.complaint_ref} · submitted ${formatDateTime(c.created_at)}`}
        actions={
          staff ? (
            <Button
              variant="outline"
              onClick={() => reanalyze.mutate({ path: { ref: complaintRef } })}
              disabled={reanalyze.isPending}
            >
              <RefreshCw /> Re-run analysis
            </Button>
          ) : undefined
        }
      />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          {staff && c.needs_review ? (
            <Alert variant="destructive">
              <Flag />
              <AlertTitle>Needs manual review</AlertTitle>
              <AlertDescription>{c.review_reason}</AlertDescription>
            </Alert>
          ) : null}
          <Card>
            <CardHeader>
              <CardTitle>Complaint</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <p className="whitespace-pre-line">{c.description}</p>
              {c.requested_resolution ? (
                <p>
                  <span className="font-medium">Requested: </span>
                  {c.requested_resolution}
                </p>
              ) : null}
              {staff ? <IntakeDetails complaint={c} /> : null}
            </CardContent>
          </Card>
          {c.approved_response ? (
            <Card>
              <CardHeader>
                <CardTitle>Approved customer response</CardTitle>
              </CardHeader>
              <CardContent className="whitespace-pre-line text-sm">
                {c.approved_response}
              </CardContent>
            </Card>
          ) : null}
          {staff ? <ValidationPanel complaintRef={complaintRef} /> : null}
          {staff && c.channel === "live_chat" ? (
            <ChatTranscript complaintRef={complaintRef} />
          ) : null}
          {staff ? (
            analysis.data?.latest ? (
              <AnalysisPanel run={analysis.data.latest} />
            ) : (
              <Card>
                <CardContent className="py-8 text-center text-sm text-muted-foreground">
                  {c.needs_review
                    ? "No successful analysis yet."
                    : "Waiting for the AI analysis to run…"}
                </CardContent>
              </Card>
            )
          ) : null}
        </div>

        <div className="space-y-6">
          {canReview ? (
            <ReviewPanel
              key={c.updated_at}
              complaint={c}
              draftResponse={analysis.data?.latest?.output?.customer_response.body}
            />
          ) : null}
          <Card>
            <CardHeader>
              <CardTitle>Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex flex-wrap gap-2">
                <StatusBadge status={c.status} />
                {staff ? <PriorityBadge priority={c.priority} /> : null}
                {staff ? <EscalationBadge level={c.escalation_level} /> : null}
                {staff ? <VerdictBadge verdict={c.verification} /> : null}
              </div>
              {staff ? <StatusControl complaint={c} /> : null}
              <dl className="space-y-2">
                <Row label="Department">{humanize(c.department_code)}</Row>
                {staff ? (
                  <>
                    <Row label="Category">
                      {humanize(c.category_code)} / {humanize(c.subcategory_code)}
                    </Row>
                    <Row label="Customer">
                      {c.customer_name} ({c.customer_ref}, {humanize(c.customer_type)})
                    </Row>
                  </>
                ) : null}
                <Row label="Channel">{humanize(c.channel)}</Row>
                {c.previous_complaint_ref ? (
                  <Row label="Follows">
                    <RefLink complaintRef={c.previous_complaint_ref} />
                  </Row>
                ) : null}
                {c.duplicate_of_ref ? (
                  <Row label="Near-duplicate of">
                    <RefLink complaintRef={c.duplicate_of_ref} /> (
                    {Math.round((c.similarity ?? 0) * 100)}%)
                  </Row>
                ) : null}
                {c.related_complaint_ref ? (
                  <Row label="Related to">
                    <RefLink complaintRef={c.related_complaint_ref} /> (
                    {Math.round((c.similarity ?? 0) * 100)}%)
                  </Row>
                ) : null}
                {staff && c.supporting_departments?.length ? (
                  <Row label="Supporting">{c.supporting_departments.map(humanize).join(", ")}</Row>
                ) : null}
                {staff ? (
                  <>
                    <Row label="SLA">
                      <SlaBadge status={c.sla_status} />
                    </Row>
                    {c.first_response_due_at ? (
                      <Row label="First response">
                        {c.first_responded_at
                          ? `Sent ${formatDateTime(c.first_responded_at)}`
                          : `Due ${formatDateTime(c.first_response_due_at)}`}
                      </Row>
                    ) : null}
                    {c.resolution_due_at ? (
                      <Row label="Resolution">
                        {c.resolved_at
                          ? `Resolved ${formatDateTime(c.resolved_at)}`
                          : `Due ${formatDateTime(c.resolution_due_at)}`}
                      </Row>
                    ) : null}
                  </>
                ) : c.resolved_at ? (
                  <Row label="Resolved">{formatDateTime(c.resolved_at)}</Row>
                ) : null}
              </dl>
            </CardContent>
          </Card>
          {c.order ? (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between gap-2">
                <CardTitle>Order {c.order.order_ref}</CardTitle>
                {isAdmin ? <DeliveryControls orderRef={c.order.order_ref} /> : null}
              </CardHeader>
              <CardContent>
                <dl className="space-y-2 text-sm">
                  <Row label="Product">{c.order.product_name}</Row>
                  <Row label="Amount">USD {c.order.amount.toFixed(2)}</Row>
                  <Row label="Shipping">{humanize(c.order.shipping_method)}</Row>
                  <Row label="Ordered">{formatDate(c.order.order_date)}</Row>
                  <Row label="Due">{formatDate(c.order.committed_delivery_date)}</Row>
                  <Row label="Delivered">{formatDate(c.order.delivered_date)}</Row>
                </dl>
              </CardContent>
            </Card>
          ) : null}
          <Card>
            <CardHeader>
              <CardTitle>Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-3 border-l pl-4 text-sm">
                {c.events.map((e, i) => (
                  <li key={i}>
                    <p>{e.message}</p>
                    <p className="text-xs text-muted-foreground">{formatDateTime(e.created_at)}</p>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}

function IntakeDetails({ complaint: c }: { complaint: ComplaintDetail }) {
  const signals = Object.entries(c.signals ?? {});
  return (
    <div className="space-y-3 border-t pt-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Deterministic intake checks (Python)
      </p>
      <div className="flex flex-wrap gap-1.5">
        {signals.length === 0 ? (
          <span className="text-muted-foreground">No risk signals.</span>
        ) : (
          signals.map(([name, matches]) => (
            <Badge
              key={name}
              variant={RISK_SIGNALS.has(name) ? "destructive" : "secondary"}
              title={`Matched: ${matches.join(", ")}`}
            >
              {SIGNAL_LABELS[name] ?? humanize(name)}
            </Badge>
          ))
        )}
      </div>
      {c.intake_warnings?.length ? (
        <p className="text-muted-foreground">{c.intake_warnings.join(" ")}</p>
      ) : null}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}

function RefLink({ complaintRef }: { complaintRef: string }) {
  return (
    <Link className="font-mono text-xs underline" href={`/complaints/${complaintRef}`}>
      {complaintRef}
    </Link>
  );
}
