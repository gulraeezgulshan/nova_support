"use client";

import { useQuery } from "@tanstack/react-query";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { listVersionChunksOptions } from "@/lib/api/generated/@tanstack/react-query.gen";

export function ChunksDialog({
  versionId,
  label,
  onClose,
}: {
  versionId: string | null;
  label: string;
  onClose: () => void;
}) {
  const chunks = useQuery({
    ...listVersionChunksOptions({ path: { version_id: versionId ?? "" } }),
    enabled: versionId !== null,
  });

  return (
    <Dialog open={versionId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Passages · {label}</DialogTitle>
          <DialogDescription>
            Each chunk keeps its document ID, version, section, heading and page for traceability.
          </DialogDescription>
        </DialogHeader>
        {chunks.isPending ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <ol className="space-y-3">
            {chunks.data?.map((chunk) => (
              <li key={chunk.chunk_code} className="rounded-lg border p-3">
                <div className="mb-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  <code className="font-mono text-foreground">{chunk.chunk_code}</code>
                  {chunk.section ? <span>§ {chunk.section}</span> : null}
                  {chunk.page_start ? (
                    <span>
                      p. {chunk.page_start}
                      {chunk.page_end && chunk.page_end !== chunk.page_start
                        ? `–${chunk.page_end}`
                        : ""}
                    </span>
                  ) : null}
                  <span>{chunk.token_count} tokens</span>
                </div>
                {chunk.heading ? <p className="text-sm font-medium">{chunk.heading}</p> : null}
                <p className="whitespace-pre-line text-sm text-muted-foreground">{chunk.content}</p>
              </li>
            ))}
          </ol>
        )}
      </DialogContent>
    </Dialog>
  );
}
