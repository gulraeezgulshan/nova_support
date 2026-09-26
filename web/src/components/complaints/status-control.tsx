"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getComplaintQueryKey,
  updateStatusMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ComplaintDetail, ComplaintStatus } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { STATUS_LABELS } from "@/lib/format";

// Mirrors the allowed transitions enforced by the API.
const NEXT: Record<ComplaintStatus, ComplaintStatus[]> = {
  new: ["assigned", "in_progress", "escalated", "awaiting_customer", "closed"],
  analyzed: ["assigned", "in_progress", "escalated", "awaiting_customer", "closed"],
  assigned: ["in_progress", "awaiting_customer", "escalated", "resolved"],
  in_progress: ["awaiting_customer", "escalated", "resolved"],
  awaiting_customer: ["in_progress", "resolved", "closed"],
  escalated: ["in_progress", "resolved"],
  resolved: ["closed", "reopened"],
  closed: ["reopened"],
  reopened: ["assigned", "in_progress", "escalated"],
};

export function StatusControl({ complaint }: { complaint: ComplaintDetail }) {
  const queryClient = useQueryClient();
  const options = NEXT[complaint.status];
  const [target, setTarget] = useState<ComplaintStatus | "">("");
  const [note, setNote] = useState("");
  const update = useMutation({
    ...updateStatusMutation(),
    onSuccess: () => {
      toast.success("Status updated");
      setTarget("");
      setNote("");
      queryClient.invalidateQueries({
        queryKey: getComplaintQueryKey({ path: { ref: complaint.complaint_ref } }),
      });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  return (
    <div className="space-y-2 border-t pt-3">
      <Select value={target} onValueChange={(v) => setTarget(v as ComplaintStatus)}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Move to…" />
        </SelectTrigger>
        <SelectContent>
          {options.map((s) => (
            <SelectItem key={s} value={s}>
              {STATUS_LABELS[s]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {target ? (
        <>
          <Input
            placeholder="Note for the customer (optional)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <Button
            size="sm"
            className="w-full"
            disabled={update.isPending}
            onClick={() =>
              update.mutate({
                path: { ref: complaint.complaint_ref },
                body: { status: target, note: note || null },
              })
            }
          >
            Update status
          </Button>
        </>
      ) : null}
    </div>
  );
}
