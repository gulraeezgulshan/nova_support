import { Badge } from "@/components/ui/badge";
import type { IngestStatus, VersionStatus } from "@/lib/api/generated/types.gen";

const VERSION_STYLES: Record<VersionStatus, string> = {
  active: "border-emerald-600/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  draft: "border-sky-600/30 bg-sky-500/10 text-sky-700 dark:text-sky-400",
  superseded: "border-amber-600/30 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  previous: "text-muted-foreground",
};

export function VersionStatusBadge({ status }: { status: VersionStatus }) {
  return (
    <Badge variant="outline" className={`capitalize ${VERSION_STYLES[status]}`}>
      {status}
    </Badge>
  );
}

export function IngestStatusBadge({
  status,
  error,
}: {
  status: IngestStatus;
  error?: string | null;
}) {
  if (status === "ready") return <span className="text-sm text-muted-foreground">Processed</span>;
  if (status === "failed") {
    return (
      <Badge variant="destructive" title={error ?? undefined}>
        Failed
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="animate-pulse capitalize">
      {status}…
    </Badge>
  );
}
