"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, FilePlus2, Mail, RotateCcw, Check } from "lucide-react";
import Link from "next/link";
import { Fragment, useState } from "react";
import { toast } from "sonner";

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
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  convertEnquiryMutation,
  listEnquiriesOptions,
  listEnquiriesQueryKey,
  updateEnquiryMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { EnquiryOut, ListEnquiriesData } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const TOPIC_LABELS: Record<string, string> = {
  order_problem: "Order problem",
  product_question: "Product question",
  business: "Business",
  feedback: "Feedback",
  other: "Other",
};
const ALL = "all";
type Topic = NonNullable<NonNullable<ListEnquiriesData["query"]>["topic"]>;

/** Contact-form messages that are not complaints: read, mark handled, or turn into a complaint. */
export function EnquiriesInbox() {
  const [status, setStatus] = useState<"new" | "handled" | typeof ALL>("new");
  const [topic, setTopic] = useState<Topic | typeof ALL>(ALL);
  const [open, setOpen] = useState<string | null>(null);
  const query = {
    ...(status !== ALL ? { status } : {}),
    ...(topic !== ALL ? { topic } : {}),
  };
  const enquiries = useQuery(listEnquiriesOptions({ query }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Select value={status} onValueChange={(v) => setStatus(v as typeof status)}>
          <SelectTrigger size="sm" className="w-36" aria-label="Status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="new">New</SelectItem>
            <SelectItem value="handled">Handled</SelectItem>
            <SelectItem value={ALL}>All</SelectItem>
          </SelectContent>
        </Select>
        <Select value={topic} onValueChange={(v) => setTopic(v as Topic | typeof ALL)}>
          <SelectTrigger size="sm" className="w-44" aria-label="Topic">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All topics</SelectItem>
            {Object.entries(TOPIC_LABELS)
              .filter(([value]) => value !== "order_problem")
              .map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
        {enquiries.data ? (
          <span className="text-sm text-muted-foreground">
            {enquiries.data.length} enquir{enquiries.data.length === 1 ? "y" : "ies"}
          </span>
        ) : null}
      </div>
      {enquiries.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : enquiries.isError ? (
        <p className="text-sm text-destructive">{apiErrorMessage(enquiries.error)}</p>
      ) : !enquiries.data.length ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-16 text-center">
          <Mail className="size-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No enquiries here.</p>
        </div>
      ) : (
        <div className="rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8" />
                <TableHead>Reference</TableHead>
                <TableHead>Received</TableHead>
                <TableHead>From</TableHead>
                <TableHead>Topic</TableHead>
                <TableHead>Message</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {enquiries.data.map((e) => (
                <Fragment key={e.ref}>
                  <TableRow
                    className="cursor-pointer"
                    onClick={() => setOpen(open === e.ref ? null : e.ref)}
                    aria-expanded={open === e.ref}
                  >
                    <TableCell>
                      <ChevronDown
                        className={cn(
                          "size-4 text-muted-foreground transition-transform",
                          open === e.ref && "rotate-180",
                        )}
                      />
                    </TableCell>
                    <TableCell className="font-mono text-xs">{e.ref}</TableCell>
                    <TableCell className="text-xs whitespace-nowrap">
                      {formatDateTime(e.created_at)}
                    </TableCell>
                    <TableCell>
                      <p className="text-sm">{e.name}</p>
                      <p className="text-xs text-muted-foreground">{e.email}</p>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{TOPIC_LABELS[e.topic] ?? e.topic}</Badge>
                    </TableCell>
                    <TableCell className="max-w-xs">
                      <p className="line-clamp-1 text-sm text-muted-foreground">{e.message}</p>
                    </TableCell>
                    <TableCell>
                      <Badge variant={e.status === "new" ? "default" : "secondary"}>
                        {e.status === "new" ? "New" : "Handled"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                  {open === e.ref ? (
                    <TableRow className="bg-muted/30 hover:bg-muted/30">
                      <TableCell />
                      <TableCell colSpan={6} className="whitespace-normal">
                        <EnquiryDetail enquiry={e} />
                      </TableCell>
                    </TableRow>
                  ) : null}
                </Fragment>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function EnquiryDetail({ enquiry: e }: { enquiry: EnquiryOut }) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: listEnquiriesQueryKey() });
  const update = useMutation({
    ...updateEnquiryMutation(),
    onSuccess: (out) => {
      toast.success(out.status === "handled" ? "Marked as handled" : "Moved back to new");
      refresh();
    },
    onError: (error) => toast.error(apiErrorMessage(error)),
  });
  const convert = useMutation({
    ...convertEnquiryMutation(),
    onSuccess: (out) => {
      toast.success(`Complaint ${out.complaint_ref} created`);
      refresh();
    },
    onError: (error) => toast.error(apiErrorMessage(error)),
  });

  return (
    <div className="space-y-4 py-2">
      <p className="text-sm whitespace-pre-wrap">{e.message}</p>
      {e.handled_at ? (
        <p className="text-xs text-muted-foreground">Handled {formatDateTime(e.handled_at)}</p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button asChild size="sm" variant="outline">
          <a href={`mailto:${e.email}?subject=${encodeURIComponent(`Re: your enquiry ${e.ref}`)}`}>
            <Mail /> Reply by e-mail
          </a>
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={update.isPending}
          onClick={() =>
            update.mutate({
              path: { ref: e.ref },
              body: { status: e.status === "new" ? "handled" : "new" },
            })
          }
        >
          {e.status === "new" ? <Check /> : <RotateCcw />}
          {e.status === "new" ? "Mark handled" : "Reopen"}
        </Button>
        {e.complaint_ref ? (
          <Button asChild size="sm" variant="secondary">
            <Link href={`/complaints/${e.complaint_ref}`}>Open {e.complaint_ref}</Link>
          </Button>
        ) : (
          <Tooltip>
            <TooltipTrigger asChild>
              <span tabIndex={e.can_convert ? undefined : 0}>
                <Button
                  size="sm"
                  disabled={!e.can_convert || convert.isPending}
                  onClick={() => convert.mutate({ path: { ref: e.ref } })}
                >
                  <FilePlus2 /> Convert to complaint
                </Button>
              </span>
            </TooltipTrigger>
            {e.can_convert ? null : (
              <TooltipContent>
                Only messages sent by a signed-in customer can become complaints.
              </TooltipContent>
            )}
          </Tooltip>
        )}
      </div>
    </div>
  );
}
