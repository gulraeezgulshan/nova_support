"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Flag } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  getVocabularyOptions,
  listComplaintsOptions,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ComplaintStatus } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { formatDate, formatDateTime, humanize, STATUS_LABELS } from "@/lib/format";

import { EscalationBadge, PriorityBadge, SLA_LABELS, SlaBadge, StatusBadge } from "./badges";
import { VerdictBadge } from "./validation-panel";

const ALL = "__all__";
const PAGE_SIZE = 25;

export function ComplaintsTable({ staff }: { staff: boolean }) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string>(ALL);
  const [priority, setPriority] = useState<string>(ALL);
  const [reviewOnly, setReviewOnly] = useState(false);
  const [sentiment, setSentiment] = useState<string>(ALL);
  const [sla, setSla] = useState<string>(ALL);
  const [escalated, setEscalated] = useState<string>(ALL);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const vocabulary = useQuery({ ...getVocabularyOptions(), enabled: staff, staleTime: Infinity });

  const query = useQuery({
    ...listComplaintsOptions({
      query: {
        q: search || undefined,
        status: status === ALL ? undefined : (status as ComplaintStatus),
        priority: priority === ALL ? undefined : priority,
        needs_review: reviewOnly ? true : undefined,
        sentiment: sentiment === ALL ? undefined : sentiment,
        sla_status: sla === ALL ? undefined : sla,
        escalated: escalated === ALL ? undefined : escalated === "yes",
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        page,
        page_size: PAGE_SIZE,
      },
    }),
    placeholderData: keepPreviousData,
  });
  const pages = Math.max(1, Math.ceil((query.data?.total ?? 0) / PAGE_SIZE));
  const reset =
    <T,>(setter: (v: T) => void) =>
    (value: T) => {
      setter(value);
      setPage(1);
    };

  return (
    <div className="space-y-4">
      {staff ? (
        <div className="flex flex-wrap gap-2">
          <Input
            className="w-64"
            placeholder="Search ref, title or customer"
            value={search}
            onChange={(e) => reset(setSearch)(e.target.value)}
          />
          <Select value={status} onValueChange={reset(setStatus)}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={priority} onValueChange={reset(setPriority)}>
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All priorities</SelectItem>
              {["P0", "P1", "P2", "P3"].map((p) => (
                <SelectItem key={p} value={p}>
                  {p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={sentiment} onValueChange={reset(setSentiment)}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All sentiments</SelectItem>
              {(vocabulary.data?.sentiments ?? []).map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={escalated} onValueChange={reset(setEscalated)}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Any escalation</SelectItem>
              <SelectItem value="yes">Escalated</SelectItem>
              <SelectItem value="no">Not escalated</SelectItem>
            </SelectContent>
          </Select>
          <Select value={sla} onValueChange={reset(setSla)}>
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Any SLA</SelectItem>
              {Object.entries(SLA_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            type="date"
            className="w-40"
            aria-label="Submitted from"
            value={dateFrom}
            onChange={(e) => reset(setDateFrom)(e.target.value)}
          />
          <Input
            type="date"
            className="w-40"
            aria-label="Submitted to"
            value={dateTo}
            onChange={(e) => reset(setDateTo)(e.target.value)}
          />
          <Button
            variant={reviewOnly ? "default" : "outline"}
            onClick={() => reset(setReviewOnly)(!reviewOnly)}
          >
            <Flag /> Needs review
          </Button>
        </div>
      ) : null}

      {query.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : query.isError ? (
        <p className="text-sm text-destructive">{apiErrorMessage(query.error)}</p>
      ) : query.data.items.length === 0 ? (
        <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
          No complaints found.
        </div>
      ) : (
        <div className="rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Reference</TableHead>
                <TableHead>Title</TableHead>
                {staff ? <TableHead>Customer</TableHead> : null}
                <TableHead>Status</TableHead>
                {staff ? (
                  <>
                    <TableHead>Category</TableHead>
                    <TableHead>Priority</TableHead>
                    <TableHead>Escalation</TableHead>
                    <TableHead>Validation</TableHead>
                    <TableHead>SLA</TableHead>
                  </>
                ) : null}
                <TableHead>Department</TableHead>
                <TableHead>Submitted</TableHead>
                {staff ? null : (
                  <>
                    <TableHead>Latest update</TableHead>
                    <TableHead>Resolution</TableHead>
                  </>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {query.data.items.map((c) => (
                <TableRow key={c.complaint_ref}>
                  <TableCell className="font-mono text-xs">
                    <Link className="hover:underline" href={`/complaints/${c.complaint_ref}`}>
                      {c.complaint_ref}
                    </Link>
                    {c.needs_review ? (
                      <Flag
                        className="ml-1 inline size-3 text-destructive"
                        aria-label="Needs review"
                      />
                    ) : null}
                  </TableCell>
                  <TableCell className="max-w-72 truncate">
                    <Link className="hover:underline" href={`/complaints/${c.complaint_ref}`}>
                      {c.title}
                    </Link>
                  </TableCell>
                  {staff ? <TableCell>{c.customer_name}</TableCell> : null}
                  <TableCell>
                    <StatusBadge status={c.status} />
                  </TableCell>
                  {staff ? (
                    <>
                      <TableCell>{humanize(c.category_code)}</TableCell>
                      <TableCell>
                        <PriorityBadge priority={c.priority} />
                      </TableCell>
                      <TableCell>
                        <EscalationBadge level={c.escalation_level} />
                      </TableCell>
                      <TableCell>
                        <VerdictBadge verdict={c.verification} />
                      </TableCell>
                      <TableCell>
                        <SlaBadge status={c.sla_status} />
                      </TableCell>
                    </>
                  ) : null}
                  <TableCell>{humanize(c.department_code)}</TableCell>
                  <TableCell className="whitespace-nowrap text-muted-foreground">
                    {formatDateTime(c.created_at)}
                  </TableCell>
                  {staff ? null : (
                    <>
                      <TableCell className="max-w-80 text-muted-foreground">
                        <p className="truncate" title={c.latest_update ?? undefined}>
                          {c.latest_update ?? "—"}
                        </p>
                        <p className="text-xs">{formatDateTime(c.latest_update_at)}</p>
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        {c.resolved_at ? `Resolved ${formatDate(c.resolved_at)}` : "Open"}
                      </TableCell>
                    </>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {pages > 1 ? (
        <div className="flex items-center justify-end gap-2 text-sm text-muted-foreground">
          <span>
            Page {page} of {pages} · {query.data?.total} complaints
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      ) : null}
    </div>
  );
}
