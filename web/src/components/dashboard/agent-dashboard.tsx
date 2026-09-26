"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
import Link from "next/link";
import { Fragment, useState } from "react";

import { KpiCard } from "@/components/analytics/charts";
import { PriorityBadge, SlaBadge, StatusBadge } from "@/components/complaints/badges";
import { VerdictBadge } from "@/components/complaints/validation-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  agentDashboardOptions,
  listDepartmentsOptions,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { AgentQueueItem } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { formatDateTime, humanize } from "@/lib/format";

const OWN = "__own__";

export function AgentDashboard({ ownDepartment }: { ownDepartment?: string | null }) {
  const [department, setDepartment] = useState<string>(OWN);
  const departments = useQuery(listDepartmentsOptions());
  const query = useQuery(
    agentDashboardOptions({ query: { department: department === OWN ? undefined : department } }),
  );
  const items = query.data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <Select value={department} onValueChange={setDepartment}>
          <SelectTrigger className="w-60" aria-label="Department">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={OWN}>
              {ownDepartment ? `My department (${ownDepartment})` : "All departments"}
            </SelectItem>
            {(departments.data ?? []).map((d) => (
              <SelectItem key={d.code} value={d.code}>
                {d.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">
          Open complaints, most urgent SLA first.
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiCard label="Open in queue" value={items.length} />
        <KpiCard
          label="SLA breached"
          value={items.filter((i) => i.sla_status === "breached").length}
          tone="danger"
        />
        <KpiCard
          label="SLA at risk"
          value={items.filter((i) => i.sla_status === "at_risk").length}
          tone="warning"
        />
        <KpiCard
          label="Escalated"
          value={items.filter((i) => (i.escalation_level ?? 0) > 0).length}
        />
      </div>

      {query.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : query.isError ? (
        <p className="text-sm text-destructive">{apiErrorMessage(query.error)}</p>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
          No open complaints.
        </div>
      ) : (
        <div className="rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8" />
                <TableHead>Complaint</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Sentiment</TableHead>
                <TableHead>Validation</TableHead>
                <TableHead>SLA</TableHead>
                <TableHead>Warnings</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <AgentRow key={item.complaint_ref} item={item} />
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function AgentRow({ item }: { item: AgentQueueItem }) {
  const [open, setOpen] = useState(false);
  return (
    <Fragment>
      <TableRow>
        <TableCell>
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            aria-label={open ? "Hide recommendation" : "Show recommendation"}
            onClick={() => setOpen(!open)}
          >
            {open ? <ChevronDown /> : <ChevronRight />}
          </Button>
        </TableCell>
        <TableCell>
          <Link
            className="font-mono text-xs hover:underline"
            href={`/complaints/${item.complaint_ref}`}
          >
            {item.complaint_ref}
          </Link>
          <p className="max-w-64 truncate text-sm">{item.title}</p>
        </TableCell>
        <TableCell>{humanize(item.category_code)}</TableCell>
        <TableCell>
          <PriorityBadge priority={item.priority} />
        </TableCell>
        <TableCell>{item.sentiment ?? "—"}</TableCell>
        <TableCell>
          <VerdictBadge verdict={item.verification} />
        </TableCell>
        <TableCell>
          <SlaBadge status={item.sla_status} />
        </TableCell>
        <TableCell>
          {item.escalation_warnings.length ? (
            <span className="flex items-center gap-1 text-xs text-amber-700 dark:text-amber-400">
              <AlertTriangle className="size-3.5" /> {item.escalation_warnings.length}
            </span>
          ) : null}
        </TableCell>
      </TableRow>
      {open ? (
        <TableRow className="bg-muted/30 hover:bg-muted/30">
          <TableCell />
          <TableCell colSpan={7} className="whitespace-normal">
            <div className="grid gap-4 py-2 text-sm lg:grid-cols-3">
              <div className="space-y-2">
                <p className="font-medium">GenAI recommendation</p>
                <p className="text-muted-foreground">{item.summary ?? "Not analysed yet."}</p>
                {item.recommended_steps.length ? (
                  <ol className="list-decimal space-y-1 pl-5">
                    {item.recommended_steps.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ol>
                ) : null}
              </div>
              <div className="space-y-2">
                <p className="font-medium">
                  Suggested response{" "}
                  {item.response_approved ? <Badge variant="secondary">Approved</Badge> : null}
                </p>
                <p className="whitespace-pre-line text-muted-foreground">
                  {item.suggested_response ?? "No draft yet."}
                </p>
              </div>
              <div className="space-y-2">
                <p className="font-medium">Escalation warnings</p>
                {item.escalation_warnings.length ? (
                  <ul className="list-disc space-y-1 pl-5">
                    {item.escalation_warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted-foreground">None.</p>
                )}
                <p className="text-xs text-muted-foreground">
                  <StatusBadge status={item.status} /> · submitted {formatDateTime(item.created_at)}
                  {item.resolution_due_at
                    ? ` · due ${formatDateTime(item.resolution_due_at)}`
                    : null}
                </p>
              </div>
            </div>
          </TableCell>
        </TableRow>
      ) : null}
    </Fragment>
  );
}
