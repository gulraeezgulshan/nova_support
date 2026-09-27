"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { simulateDeliveryMutation } from "@/lib/api/generated/@tanstack/react-query.gen";
import type { SimulateIn } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";

const OPTIONS: { label: string; body: SimulateIn }[] = [
  { label: "Delivered on time", body: { outcome: "on_time", days: 0 } },
  { label: "Delivered 2 days late", body: { outcome: "late", days: 2 } },
  { label: "Delivered 5 days late", body: { outcome: "late", days: 5 } },
  { label: "Delivered 8 days late", body: { outcome: "late", days: 8 } },
  { label: "Delivered damaged", body: { outcome: "damaged", days: 0 } },
  { label: "Lost in transit", body: { outcome: "lost", days: 0 } },
];

/** Admin-only demo control: make a delivery outcome "just happen" (the API checks the role). */
export function DeliveryControls({
  orderRef,
  onChanged,
}: {
  orderRef: string;
  onChanged?: () => void;
}) {
  const queryClient = useQueryClient();
  const simulate = useMutation({
    ...simulateDeliveryMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries();
      onChanged?.();
      toast.success("Delivery outcome set");
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" disabled={simulate.isPending}>
          <FlaskConical /> Demo
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Simulate delivery</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {OPTIONS.map((o) => (
          <DropdownMenuItem
            key={o.label}
            onSelect={() => simulate.mutate({ path: { order_ref: orderRef }, body: o.body })}
          >
            {o.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
