"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { reviewQueueOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ReviewStatus } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { formatDateTime, humanize } from "@/lib/format";

import { EscalationBadge, PriorityBadge } from "./badges";

export function ReviewQueue() {
  const [status, setStatus] = useState<ReviewStatus>("open");
  const queue = useQuery({ ...reviewQueueOptions({ query: { status } }), refetchInterval: 15_000 });

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {(["open", "resolved"] as const).map((s) => (
          <Button
            key={s}
            variant={status === s ? "default" : "outline"}
            size="sm"
            onClick={() => setStatus(s)}
          >
            {humanize(s)}
          </Button>
        ))}
      </div>
      {queue.isPending ? (
        <Skeleton className="h-64" />
      ) : queue.isError ? (
        <p className="text-sm text-destructive">{apiErrorMessage(queue.error)}</p>
      ) : queue.data.length === 0 ? (
        <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
          {status === "open" ? "Nothing waiting for review." : "No resolved reviews yet."}
        </div>
      ) : (
        <div className="rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Complaint</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Category / department</TableHead>
                <TableHead>Why it needs review</TableHead>
                <TableHead>{status === "open" ? "Waiting since" : "Resolved"}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {queue.data.map((task) => (
                <TableRow key={task.id}>
                  <TableCell className="max-w-64 align-top">
                    <Link
                      className="font-mono text-xs hover:underline"
                      href={`/complaints/${task.complaint.complaint_ref}`}
                    >
                      {task.complaint.complaint_ref}
                    </Link>
                    <p className="truncate">{task.complaint.title}</p>
                    <p className="text-xs text-muted-foreground">{task.complaint.customer_name}</p>
                  </TableCell>
                  <TableCell className="align-top">
                    <div className="flex flex-col items-start gap-1">
                      <PriorityBadge priority={task.complaint.priority} />
                      <EscalationBadge level={task.complaint.escalation_level} />
                    </div>
                  </TableCell>
                  <TableCell className="align-top text-sm">
                    {humanize(task.complaint.category_code)}
                    <p className="text-xs text-muted-foreground">
                      {humanize(task.complaint.department_code)}
                    </p>
                  </TableCell>
                  <TableCell className="max-w-md align-top">
                    <ul className="list-disc space-y-1 pl-4 text-xs">
                      {task.reasons.slice(0, 4).map((r) => (
                        <li key={r}>{r}</li>
                      ))}
                      {task.reasons.length > 4 ? <li>+{task.reasons.length - 4} more</li> : null}
                    </ul>
                  </TableCell>
                  <TableCell className="whitespace-nowrap align-top text-xs text-muted-foreground">
                    {formatDateTime(status === "open" ? task.created_at : task.resolved_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
