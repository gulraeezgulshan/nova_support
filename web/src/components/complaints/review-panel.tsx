"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  getComplaintAnalysisQueryKey,
  getComplaintQueryKey,
  listCategoriesOptions,
  listDecisionsOptions,
  listDecisionsQueryKey,
  listDepartmentsOptions,
  reviewComplaintMutation,
  reviewQueueQueryKey,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ComplaintDetail, ReviewAction } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { ESCALATION_LABELS, formatDateTime, humanize } from "@/lib/format";

const ACTIONS: { value: ReviewAction; label: string; hint: string }[] = [
  { value: "approve", label: "Approve", hint: "Approve the drafted customer response as it is." },
  {
    value: "modify",
    label: "Modify response",
    hint: "Edit the customer response, then approve it.",
  },
  { value: "reject", label: "Reject", hint: "Reject the AI recommendation and handle manually." },
  {
    value: "reclassify",
    label: "Reclassify",
    hint: "Change the category; the rules are re-applied.",
  },
  { value: "reassign", label: "Reassign", hint: "Move the complaint to another department." },
  { value: "escalate", label: "Escalate", hint: "Raise the escalation level (never lowered)." },
  { value: "regenerate", label: "Regenerate", hint: "Run the GenAI analysis again." },
  { value: "comment", label: "Comment", hint: "Add an internal note." },
];

export function ReviewPanel({
  complaint,
  draftResponse,
}: {
  complaint: ComplaintDetail;
  draftResponse?: string;
}) {
  const queryClient = useQueryClient();
  const ref = complaint.complaint_ref;
  const [action, setAction] = useState<ReviewAction>("approve");
  const [comment, setComment] = useState("");
  const [response, setResponse] = useState(complaint.approved_response ?? draftResponse ?? "");
  const [category, setCategory] = useState(complaint.category_code ?? "");
  const [subcategory, setSubcategory] = useState(complaint.subcategory_code ?? "");
  const [department, setDepartment] = useState(complaint.department_code ?? "");
  const [level, setLevel] = useState(String(Math.max(1, complaint.escalation_level ?? 0)));
  const categories = useQuery({ ...listCategoriesOptions(), enabled: action === "reclassify" });
  const departments = useQuery({ ...listDepartmentsOptions(), enabled: action === "reassign" });
  const decisions = useQuery(listDecisionsOptions({ path: { ref } }));

  const review = useMutation({
    ...reviewComplaintMutation(),
    onSuccess: () => {
      toast.success("Decision recorded");
      setComment("");
      for (const key of [
        getComplaintQueryKey({ path: { ref } }),
        listDecisionsQueryKey({ path: { ref } }),
        getComplaintAnalysisQueryKey({ path: { ref } }),
        reviewQueueQueryKey(),
      ]) {
        queryClient.invalidateQueries({ queryKey: key });
      }
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  function submit() {
    review.mutate({
      path: { ref },
      body: {
        action,
        comment: comment || null,
        response_body: action === "modify" || action === "approve" ? response || null : null,
        category: action === "reclassify" ? category : null,
        subcategory: action === "reclassify" ? subcategory : null,
        department: action === "reassign" ? department : null,
        escalation_level: action === "escalate" ? Number(level) : null,
      },
    });
  }

  const subcategories =
    categories.data?.find((c) => c.code === category)?.subcategories.filter((s) => s.is_active) ??
    [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Reviewer decision</CardTitle>
        <CardDescription>
          The original AI and Python recommendations are kept; every decision is recorded with its
          before and after state.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Action</Label>
          <Select value={action} onValueChange={(v) => setAction(v as ReviewAction)}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ACTIONS.map((a) => (
                <SelectItem key={a.value} value={a.value}>
                  {a.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            {ACTIONS.find((a) => a.value === action)?.hint}
          </p>
        </div>

        {action === "modify" || action === "approve" ? (
          <div className="space-y-2">
            <Label>Customer response</Label>
            <Textarea
              rows={8}
              value={response}
              onChange={(e) => setResponse(e.target.value)}
              readOnly={action === "approve"}
            />
          </div>
        ) : null}

        {action === "reclassify" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Select
              value={category}
              onValueChange={(v) => {
                setCategory(v);
                setSubcategory("");
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                {categories.data
                  ?.filter((c) => c.is_active)
                  .map((c) => (
                    <SelectItem key={c.code} value={c.code}>
                      {c.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
            <Select value={subcategory} onValueChange={setSubcategory}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Subcategory" />
              </SelectTrigger>
              <SelectContent>
                {subcategories.map((s) => (
                  <SelectItem key={s.code} value={s.code}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}

        {action === "reassign" ? (
          <Select value={department} onValueChange={setDepartment}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Department" />
            </SelectTrigger>
            <SelectContent>
              {departments.data?.map((d) => (
                <SelectItem key={d.code} value={d.code}>
                  {d.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : null}

        {action === "escalate" ? (
          <Select value={level} onValueChange={setLevel}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[1, 2, 3, 4, 5].map((l) => (
                <SelectItem
                  key={l}
                  value={String(l)}
                  disabled={l < (complaint.escalation_level ?? 0)}
                >
                  L{l} · {ESCALATION_LABELS[l]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : null}

        <div className="space-y-2">
          <Label>
            Comment {action === "reject" || action === "comment" ? "(required)" : "(optional)"}
          </Label>
          <Textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} />
        </div>

        <Button onClick={submit} disabled={review.isPending} className="w-full">
          {review.isPending
            ? "Saving…"
            : `Record: ${ACTIONS.find((a) => a.value === action)?.label}`}
        </Button>

        {decisions.data?.length ? (
          <div className="space-y-2 border-t pt-4">
            <p className="text-sm font-medium">Decision history</p>
            <ol className="space-y-2 text-xs">
              {decisions.data.map((d) => (
                <li key={d.id} className="rounded-md border p-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">{humanize(d.action)}</Badge>
                    <span className="text-muted-foreground">{formatDateTime(d.created_at)}</span>
                  </div>
                  {d.comment ? <p className="mt-1">{d.comment}</p> : null}
                  <DiffLine before={d.before} after={d.after} />
                </li>
              ))}
            </ol>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function DiffLine({
  before,
  after,
}: {
  before: Record<string, unknown>;
  after: Record<string, unknown>;
}) {
  const changed = Object.keys(after).filter(
    (k) => k !== "approved_response" && JSON.stringify(before[k]) !== JSON.stringify(after[k]),
  );
  if (!changed.length) return null;
  return (
    <p className="mt-1 text-muted-foreground">
      {changed
        .map((k) => `${humanize(k)}: ${String(before[k] ?? "—")} → ${String(after[k] ?? "—")}`)
        .join(" · ")}
    </p>
  );
}
