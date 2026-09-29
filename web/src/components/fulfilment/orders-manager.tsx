"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { orderReceipt } from "@/lib/api/generated/sdk.gen";
import {
  staffOrderActionMutation,
  staffOrderOptions,
  staffOrdersOptions,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { formatLocal, money } from "@/lib/currency";
import { saveBlob } from "@/lib/download";
import { formatDate, formatDateTime } from "@/lib/format";

const STAGES = [
  "placed",
  "packed",
  "shipped",
  "out_for_delivery",
  "delivered",
  "lost",
  "cancelled",
  "return_requested",
  "return_refused",
  "returned",
];
const label = (s: string) => s.replaceAll("_", " ");

type Action =
  "advance" | "delay" | "lose" | "cancel" | "approve_return" | "refuse_return" | "resume_auto";
const ACTIONS: Record<string, { action: Action; text: string }[]> = {
  placed: [
    { action: "advance", text: "Mark packed" },
    { action: "cancel", text: "Cancel" },
  ],
  packed: [
    { action: "advance", text: "Mark shipped" },
    { action: "cancel", text: "Cancel" },
  ],
  shipped: [
    { action: "advance", text: "Out for delivery" },
    { action: "delay", text: "Delay" },
    { action: "lose", text: "Mark lost" },
  ],
  out_for_delivery: [
    { action: "advance", text: "Mark delivered" },
    { action: "delay", text: "Delay" },
    { action: "lose", text: "Mark lost" },
  ],
  return_requested: [
    { action: "approve_return", text: "Approve return" },
    { action: "refuse_return", text: "Refuse return" },
  ],
};

export function OrdersManager() {
  const queryClient = useQueryClient();
  const [stage, setStage] = useState("all");
  const [q, setQ] = useState("");
  const [needsAction, setNeedsAction] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [newDate, setNewDate] = useState("");
  const [daysLate, setDaysLate] = useState(0);
  const list = useQuery(
    staffOrdersOptions({
      query: {
        stage: stage === "all" ? undefined : stage,
        q: q || undefined,
        needs_action: needsAction,
      },
    }),
  );
  const detail = useQuery({
    ...staffOrderOptions({ path: { ref: open ?? "" } }),
    enabled: Boolean(open),
  });
  const act = useMutation({
    ...staffOrderActionMutation(),
    onSuccess: () => {
      toast.success("Order updated");
      queryClient.invalidateQueries();
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });
  const run = (action: Action) =>
    open &&
    act.mutate({
      path: { ref: open },
      body: {
        action,
        new_date: action === "delay" ? newDate || null : null,
        days_late: action === "advance" ? daysLate : 0,
      },
    });

  async function receipt(ref: string) {
    try {
      const { data } = await orderReceipt({ path: { ref }, parseAs: "blob", throwOnError: true });
      saveBlob(data as Blob, `receipt-${ref}.pdf`);
    } catch (err) {
      toast.error(apiErrorMessage(err));
    }
  }

  const o = detail.data;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Input
          className="max-w-xs"
          placeholder="Search order, customer or product"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <Select value={stage} onValueChange={setStage}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All stages</SelectItem>
            {STAGES.map((s) => (
              <SelectItem key={s} value={s}>
                {label(s)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <label className="flex items-center gap-2 text-sm">
          <Switch checked={needsAction} onCheckedChange={setNeedsAction} /> Needs action
        </label>
      </div>
      {list.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : list.isError ? (
        <p className="text-sm text-destructive">{apiErrorMessage(list.error)}</p>
      ) : (
        <div className="rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Order</TableHead>
                <TableHead>Customer</TableHead>
                <TableHead>Product</TableHead>
                <TableHead>Stage</TableHead>
                <TableHead>Promised</TableHead>
                <TableHead className="text-right">Paid</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.data.map((r) => (
                <TableRow
                  key={r.order_ref}
                  className="cursor-pointer"
                  onClick={() => setOpen(r.order_ref)}
                >
                  <TableCell className="font-mono text-xs">{r.order_ref}</TableCell>
                  <TableCell>{r.customer_name}</TableCell>
                  <TableCell>{r.product_name}</TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        r.stage === "return_requested" || r.expected_delivery_date
                          ? "destructive"
                          : "secondary"
                      }
                    >
                      {label(r.stage)}
                    </Badge>
                    {r.manual_hold ? (
                      <span className="ml-1 text-xs text-muted-foreground">(manual)</span>
                    ) : null}
                  </TableCell>
                  <TableCell>{formatDate(r.committed_delivery_date)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatLocal(r)}</TableCell>
                </TableRow>
              ))}
              {list.data.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-sm text-muted-foreground">
                    No orders.
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      )}
      <Sheet open={Boolean(open)} onOpenChange={(v) => !v && setOpen(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
          <SheetHeader>
            <SheetTitle>{open}</SheetTitle>
          </SheetHeader>
          {!o ? (
            <Skeleton className="m-4 h-64" />
          ) : (
            <div className="space-y-5 p-4 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <span className="text-muted-foreground">Customer</span>
                <span>
                  {o.customer_name} · {o.customer_email ?? "no e-mail"}
                </span>
                <span className="text-muted-foreground">Product</span>
                <span>
                  {o.product_name} × {o.quantity}
                </span>
                <span className="text-muted-foreground">Paid</span>
                <span>
                  {formatLocal(o)} (USD reference {money(o.amount, "USD")})
                </span>
                <span className="text-muted-foreground">Promised</span>
                <span>
                  {formatDate(o.committed_delivery_date)}
                  {o.expected_delivery_date
                    ? `, now expected ${formatDate(o.expected_delivery_date)}`
                    : ""}
                </span>
                <span className="text-muted-foreground">Complaints</span>
                <span>{o.complaint_refs.length ? o.complaint_refs.join(", ") : "—"}</span>
              </div>
              <ul className="space-y-1 border-l pl-3 text-xs">
                {o.events.map((e) => (
                  <li key={`${e.stage}-${e.created_at}`}>
                    <span className="font-medium">{label(e.stage)}</span>
                    <span className="text-muted-foreground">
                      {" "}
                      · {e.actor} · {formatDateTime(e.created_at)}
                      {e.note ? ` · ${e.note}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="space-y-2">
                {o.stage === "out_for_delivery" ? (
                  <label className="flex items-center gap-2 text-xs">
                    Deliver
                    <Input
                      type="number"
                      min={0}
                      max={30}
                      className="w-16"
                      value={daysLate}
                      onChange={(e) => setDaysLate(Number(e.target.value))}
                    />
                    business days late (demo)
                  </label>
                ) : null}
                {o.stage === "shipped" || o.stage === "out_for_delivery" ? (
                  <label className="flex items-center gap-2 text-xs">
                    New expected date
                    <Input
                      type="date"
                      className="w-40"
                      value={newDate}
                      onChange={(e) => setNewDate(e.target.value)}
                    />
                  </label>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  {(ACTIONS[o.stage] ?? []).map((a) => (
                    <Button
                      key={a.action}
                      size="sm"
                      variant={a.action === "lose" || a.action === "cancel" ? "outline" : "default"}
                      disabled={act.isPending || (a.action === "delay" && !newDate)}
                      onClick={() => run(a.action)}
                    >
                      {a.text}
                    </Button>
                  ))}
                  {o.manual_hold ? (
                    <Button size="sm" variant="ghost" onClick={() => run("resume_auto")}>
                      Resume automatic progress
                    </Button>
                  ) : null}
                  <Button size="sm" variant="ghost" onClick={() => receipt(o.order_ref)}>
                    Receipt
                  </Button>
                </div>
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
