import { Badge } from "@/components/ui/badge";
import type { ComplaintStatus } from "@/lib/api/generated/types.gen";
import { ESCALATION_LABELS, STATUS_LABELS } from "@/lib/format";
import { cn } from "@/lib/utils";

const PRIORITY_STYLES: Record<string, string> = {
  P0: "border-red-600/40 bg-red-500/10 text-red-700 dark:text-red-400",
  P1: "border-orange-600/40 bg-orange-500/10 text-orange-700 dark:text-orange-400",
  P2: "border-sky-600/30 bg-sky-500/10 text-sky-700 dark:text-sky-400",
  P3: "text-muted-foreground",
};

export function PriorityBadge({ priority }: { priority?: string | null }) {
  if (!priority) return <span className="text-muted-foreground">—</span>;
  return (
    <Badge variant="outline" className={cn("font-mono", PRIORITY_STYLES[priority])}>
      {priority}
    </Badge>
  );
}

export function StatusBadge({ status }: { status: ComplaintStatus }) {
  const muted = status === "closed" || status === "resolved";
  return <Badge variant={muted ? "secondary" : "outline"}>{STATUS_LABELS[status]}</Badge>;
}

export function EscalationBadge({ level }: { level?: number | null }) {
  if (!level) return null;
  return (
    <Badge
      variant="outline"
      className={cn(
        level >= 4
          ? "border-red-600/40 bg-red-500/10 text-red-700 dark:text-red-400"
          : "border-amber-600/40 bg-amber-500/10 text-amber-700 dark:text-amber-400",
      )}
    >
      L{level} · {ESCALATION_LABELS[level]}
    </Badge>
  );
}

const SLA_STYLES: Record<string, string> = {
  on_track: "border-emerald-600/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  at_risk: "border-amber-600/40 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  breached: "border-red-600/40 bg-red-500/10 text-red-700 dark:text-red-400",
  met: "text-muted-foreground",
  missed: "border-red-600/30 text-red-700 dark:text-red-400",
};
export const SLA_LABELS: Record<string, string> = {
  pending: "Awaiting triage",
  on_track: "On track",
  at_risk: "At risk",
  breached: "Breached",
  met: "Met",
  missed: "Missed",
};

export function SlaBadge({ status }: { status?: string | null }) {
  if (!status || status === "pending") return <span className="text-muted-foreground">—</span>;
  return (
    <Badge variant="outline" className={SLA_STYLES[status]}>
      {SLA_LABELS[status] ?? status}
    </Badge>
  );
}
