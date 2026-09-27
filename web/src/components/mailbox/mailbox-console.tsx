"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
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
  listInboundEmailsOptions,
  listOutboundEmailsOptions,
  mailboxStatusOptions,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { formatDateTime } from "@/lib/format";

import { OUTCOME_LABELS } from "./labels";
import { ProcessEmailDialog } from "./process-email-dialog";

const KIND_LABELS: Record<string, string> = {
  acknowledgement: "Acknowledgement",
  holding: "Holding message",
  reply: "Reply",
  rejected: "More detail needed",
  duplicate: "Duplicate notice",
};
const STATUS_TONE: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  sent: "default",
  queued: "secondary",
  failed: "destructive",
  not_configured: "outline",
};

function ComplaintLink({ complaintRef }: { complaintRef: string | null | undefined }) {
  return complaintRef ? (
    <Link href={`/complaints/${complaintRef}`} className="font-mono text-xs underline">
      {complaintRef}
    </Link>
  ) : (
    <span className="text-muted-foreground">—</span>
  );
}

function MailboxStatus() {
  const status = useQuery({ ...mailboxStatusOptions(), refetchInterval: 30_000 });
  if (status.isPending) return <Skeleton className="h-16" />;
  if (status.isError)
    return <p className="text-sm text-destructive">{apiErrorMessage(status.error)}</p>;
  const s = status.data;
  const [Icon, tone, text] = !s.configured
    ? [
        Info,
        "text-amber-600",
        "The mailbox is not configured. Add the MAIL_* settings to .env to receive e-mails automatically; you can still process e-mails by hand.",
      ]
    : s.last_error
      ? [AlertTriangle, "text-destructive", `Last check had a problem: ${s.last_error}`]
      : [
          CheckCircle2,
          "text-emerald-600",
          `Checking ${s.address} every minute${
            s.last_check_at ? ` · last check ${formatDateTime(s.last_check_at)}` : ""
          }.`,
        ];
  return (
    <Card>
      <CardContent className="flex items-start gap-3 py-4 text-sm">
        <Icon className={`mt-0.5 size-4 shrink-0 ${tone}`} />
        <p>{text}</p>
      </CardContent>
    </Card>
  );
}

function Received() {
  const inbound = useQuery({ ...listInboundEmailsOptions(), refetchInterval: 30_000 });
  if (inbound.isPending) return <Skeleton className="h-48" />;
  if (inbound.isError)
    return <p className="text-sm text-destructive">{apiErrorMessage(inbound.error)}</p>;
  if (!inbound.data.length)
    return <p className="py-10 text-center text-sm text-muted-foreground">No e-mails yet.</p>;
  return (
    <div className="rounded-xl border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Received</TableHead>
            <TableHead>From</TableHead>
            <TableHead>Subject</TableHead>
            <TableHead>Outcome</TableHead>
            <TableHead>Complaint</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {inbound.data.map((e) => (
            <TableRow key={e.id}>
              <TableCell className="text-xs whitespace-nowrap">
                {formatDateTime(e.created_at)}
                {e.via === "manual" ? (
                  <Badge variant="outline" className="ml-2 text-[10px]">
                    by hand
                  </Badge>
                ) : null}
              </TableCell>
              <TableCell>
                <p className="text-sm">{e.from_name ?? e.from_address}</p>
                {e.from_name ? (
                  <p className="text-xs text-muted-foreground">{e.from_address}</p>
                ) : null}
              </TableCell>
              <TableCell className="max-w-xs truncate text-sm">{e.subject || "—"}</TableCell>
              <TableCell>
                <Badge
                  variant={e.outcome === "failed" ? "destructive" : "secondary"}
                  title={e.reason ?? undefined}
                >
                  {OUTCOME_LABELS[e.outcome] ?? e.outcome}
                </Badge>
                {e.reason && e.outcome !== "filed" ? (
                  <p className="mt-1 max-w-xs text-xs text-muted-foreground">{e.reason}</p>
                ) : null}
              </TableCell>
              <TableCell>
                <ComplaintLink complaintRef={e.complaint_ref} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function Sent() {
  const outbound = useQuery({ ...listOutboundEmailsOptions(), refetchInterval: 30_000 });
  if (outbound.isPending) return <Skeleton className="h-48" />;
  if (outbound.isError)
    return <p className="text-sm text-destructive">{apiErrorMessage(outbound.error)}</p>;
  if (!outbound.data.length)
    return <p className="py-10 text-center text-sm text-muted-foreground">Nothing sent yet.</p>;
  return (
    <div className="rounded-xl border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Queued</TableHead>
            <TableHead>To</TableHead>
            <TableHead>Kind</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Complaint</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {outbound.data.map((e) => (
            <TableRow key={e.id}>
              <TableCell className="text-xs whitespace-nowrap">
                {formatDateTime(e.created_at)}
              </TableCell>
              <TableCell className="text-sm">{e.to_address}</TableCell>
              <TableCell className="text-sm">{KIND_LABELS[e.kind] ?? e.kind}</TableCell>
              <TableCell>
                <Badge variant={STATUS_TONE[e.status] ?? "outline"} title={e.error ?? undefined}>
                  {e.status === "not_configured" ? "Not sent (no mailbox)" : e.status}
                </Badge>
                {e.error ? (
                  <p className="mt-1 max-w-xs text-xs text-muted-foreground">{e.error}</p>
                ) : null}
              </TableCell>
              <TableCell>
                <ComplaintLink complaintRef={e.complaint_ref} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function MailboxConsole() {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <MailboxStatus />
        </div>
        <ProcessEmailDialog />
      </div>
      <Tabs defaultValue="received">
        <TabsList>
          <TabsTrigger value="received">Received</TabsTrigger>
          <TabsTrigger value="sent">Sent</TabsTrigger>
        </TabsList>
        <TabsContent value="received" className="pt-2">
          <Received />
        </TabsContent>
        <TabsContent value="sent" className="pt-2">
          <Sent />
        </TabsContent>
      </Tabs>
    </div>
  );
}
