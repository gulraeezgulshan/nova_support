"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { orderReceipt } from "@/lib/api/generated/sdk.gen";
import {
  cancelOrderMutation,
  myShopOrdersQueryKey,
  orderEventsOptions,
  requestReturnMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ShopOrderOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { saveBlob } from "@/lib/download";
import { formatDate, formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const STEPS = ["placed", "packed", "shipped", "out_for_delivery", "delivered"] as const;
const LABEL: Record<string, string> = {
  placed: "Placed",
  packed: "Packed",
  shipped: "Shipped",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  lost: "Lost in transit",
  cancelled: "Cancelled",
  return_requested: "Return requested",
  return_refused: "Return refused",
  returned: "Returned",
  delayed: "Delayed",
};
const RETURN_DAYS = 30;

export function OrderTracker({ order: o }: { order: ShopOrderOut }) {
  const queryClient = useQueryClient();
  const [returning, setReturning] = useState(false);
  const [openedAt] = useState(() => Date.now()); // read once, not on every render
  const [reason, setReason] = useState("");
  const history = useQuery(orderEventsOptions({ path: { ref: o.order_ref } }));
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: myShopOrdersQueryKey() });
    history.refetch();
  };
  const onError = (err: unknown) => toast.error(apiErrorMessage(err));
  const cancel = useMutation({
    ...cancelOrderMutation(),
    onSuccess: () => {
      toast.success("Order cancelled");
      refresh();
    },
    onError,
  });
  const ret = useMutation({
    ...requestReturnMutation(),
    onSuccess: () => {
      toast.success("Return requested");
      setReturning(false);
      refresh();
    },
    onError,
  });

  // Return stages come after delivery: the five steps are all done.
  const afterDelivery = ["return_requested", "return_refused", "returned"].includes(o.stage);
  const reached = afterDelivery
    ? STEPS.length - 1
    : STEPS.indexOf(o.stage as (typeof STEPS)[number]);
  const endLabel =
    afterDelivery || (reached === -1 && o.stage !== "placed") ? LABEL[o.stage] : null;
  const delivered = o.delivered_date ? new Date(o.delivered_date) : null;
  const canReturn =
    o.stage === "delivered" &&
    delivered !== null &&
    (openedAt - delivered.getTime()) / 86_400_000 <= RETURN_DAYS;

  async function receipt() {
    try {
      const { data } = await orderReceipt({
        path: { ref: o.order_ref },
        parseAs: "blob",
        throwOnError: true,
      });
      saveBlob(data as Blob, `receipt-${o.order_ref}.pdf`);
    } catch (err) {
      onError(err);
    }
  }

  return (
    <div className="mt-3 space-y-3">
      <ol className="flex flex-wrap items-center gap-2 text-[11px]" aria-label="Order progress">
        {STEPS.map((step, i) => (
          <li key={step} className="flex items-center gap-2">
            <span
              className={cn(
                "rounded-full px-2 py-0.5",
                i <= reached ? "bg-brand text-brand-foreground" : "bg-muted text-muted-foreground",
              )}
            >
              {LABEL[step]}
            </span>
            {i < STEPS.length - 1 ? <span className="h-px w-4 bg-border" /> : null}
          </li>
        ))}
        {endLabel ? (
          <li className="rounded-full bg-destructive/10 px-2 py-0.5 text-destructive">
            {endLabel}
          </li>
        ) : null}
      </ol>
      <p className="text-xs text-muted-foreground">
        Promised by {formatDate(o.committed_delivery_date)}
        {o.expected_delivery_date ? ` · now expected ${formatDate(o.expected_delivery_date)}` : ""}
      </p>
      {history.data?.length ? (
        <ul className="space-y-1 border-l pl-3 text-xs">
          {history.data.map((e) => (
            <li key={`${e.stage}-${e.created_at}`}>
              <span className="font-medium">{LABEL[e.stage] ?? e.stage}</span>
              <span className="text-muted-foreground">
                {" "}
                · {formatDateTime(e.created_at)}
                {e.note ? ` · ${e.note}` : ""}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {o.stage === "placed" || o.stage === "packed" ? (
          <Button
            size="sm"
            variant="outline"
            disabled={cancel.isPending}
            onClick={() => cancel.mutate({ path: { ref: o.order_ref } })}
          >
            Cancel order
          </Button>
        ) : null}
        {canReturn ? (
          <Button size="sm" variant="outline" onClick={() => setReturning((v) => !v)}>
            Request a return
          </Button>
        ) : null}
        <Button size="sm" variant="ghost" onClick={receipt}>
          Receipt
        </Button>
      </div>
      {returning ? (
        <div className="space-y-2">
          <Textarea
            value={reason}
            maxLength={500}
            placeholder="What is wrong with it? (at least 10 characters)"
            onChange={(e) => setReason(e.target.value)}
          />
          <Button
            size="sm"
            disabled={reason.trim().length < 10 || ret.isPending}
            onClick={() =>
              ret.mutate({ path: { ref: o.order_ref }, body: { reason: reason.trim() } })
            }
          >
            Send return request
          </Button>
        </div>
      ) : null}
    </div>
  );
}
