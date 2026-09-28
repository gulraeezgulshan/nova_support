"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, MoreHorizontal } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
  activateVersionMutation,
  listDocumentsOptions,
  listDocumentsQueryKey,
  reprocessVersionMutation,
  retireVersionMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import { downloadVersionFile } from "@/lib/api/generated/sdk.gen";
import type { DocumentOut, DocumentVersionOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { saveBlob } from "@/lib/download";

import { ChunksDialog } from "./chunks-dialog";
import { IngestStatusBadge, VersionStatusBadge } from "./status-badges";

const isProcessing = (documents: DocumentOut[] | undefined) =>
  documents?.some((d) =>
    d.versions.some((v) => v.ingest_status === "pending" || v.ingest_status === "processing"),
  ) ?? false;

// Shown in a browser tab; anything else (e.g. Word) is downloaded.
const VIEWABLE = new Set(["application/pdf", "text/plain", "text/markdown"]);

/** Open the original uploaded file: PDFs and text in a new tab, other files as a download. */
async function openOriginal(version: DocumentVersionOut) {
  const viewable = VIEWABLE.has(version.media_type);
  // Open the tab before the download finishes, or the browser treats it as a pop-up.
  const tab = viewable ? window.open("", "_blank") : null;
  try {
    const { data } = await downloadVersionFile({
      path: { version_id: version.id },
      parseAs: "blob",
      throwOnError: true,
    });
    const blob = data as Blob;
    if (tab) {
      tab.location.href = URL.createObjectURL(blob);
    } else {
      saveBlob(blob, version.file_name);
    }
  } catch (err) {
    tab?.close();
    toast.error(apiErrorMessage(err, "Could not open the document."));
  }
}

export function DocumentsTable({ canManage }: { canManage: boolean }) {
  const queryClient = useQueryClient();
  const [chunksFor, setChunksFor] = useState<{ id: string; label: string } | null>(null);
  const documents = useQuery({
    ...listDocumentsOptions(),
    // Poll while any upload is still being processed by the worker.
    refetchInterval: (query) => (isProcessing(query.state.data) ? 2000 : false),
  });

  const onDone = (message: string) => ({
    onSuccess: () => {
      toast.success(message);
      queryClient.invalidateQueries({ queryKey: listDocumentsQueryKey() });
    },
    onError: (err: unknown) => toast.error(apiErrorMessage(err)),
  });
  const activate = useMutation({ ...activateVersionMutation(), ...onDone("Version activated") });
  const retire = useMutation({ ...retireVersionMutation(), ...onDone("Version retired") });
  const reprocess = useMutation({
    ...reprocessVersionMutation(),
    ...onDone("Reprocessing started"),
  });

  if (documents.isPending) return <Skeleton className="h-64 w-full" />;
  if (documents.isError) {
    return <p className="text-sm text-destructive">{apiErrorMessage(documents.error)}</p>;
  }
  if (documents.data.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
        No documents yet.{" "}
        {canManage ? "Upload your first policy to start grounding recommendations." : null}
      </div>
    );
  }

  const rows = documents.data.flatMap((doc) =>
    doc.versions.map((version, index) => ({ doc, version, first: index === 0 })),
  );

  const actions = (doc: DocumentOut, v: DocumentVersionOut) => {
    const path = { path: { version_id: v.id } };
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="Version actions">
            <MoreHorizontal />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => openOriginal(v)}>
            {VIEWABLE.has(v.media_type) ? "Open document" : "Download document"}
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={v.ingest_status !== "ready"}
            onSelect={() => setChunksFor({ id: v.id, label: `${doc.doc_code} v${v.version}` })}
          >
            View passages
          </DropdownMenuItem>
          {canManage ? (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                disabled={v.status === "active" || v.ingest_status !== "ready"}
                onSelect={() => activate.mutate(path)}
              >
                Make active
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled={v.status !== "active"}
                onSelect={() => retire.mutate(path)}
              >
                Retire (no replacement)
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled={v.ingest_status !== "failed"}
                onSelect={() => reprocess.mutate(path)}
              >
                Reprocess
              </DropdownMenuItem>
            </>
          ) : null}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  };

  return (
    <>
      <div className="rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Document</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Processing</TableHead>
              <TableHead>Effective</TableHead>
              <TableHead className="text-right">Passages</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(({ doc, version, first }) => (
              <TableRow key={version.id} className={first ? "" : "text-muted-foreground"}>
                <TableCell>
                  {first ? (
                    <div>
                      <button
                        type="button"
                        onClick={() => openOriginal(version)}
                        className="inline-flex items-center gap-1.5 text-left font-medium text-foreground hover:text-brand hover:underline"
                        title={`Open ${version.file_name}`}
                      >
                        <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                        {doc.title}
                      </button>
                      <div className="text-xs text-muted-foreground">
                        <code>{doc.doc_code}</code> · {doc.doc_type.replaceAll("_", " ")}
                      </div>
                    </div>
                  ) : null}
                </TableCell>
                <TableCell>v{version.version}</TableCell>
                <TableCell>
                  <VersionStatusBadge status={version.status} />
                </TableCell>
                <TableCell>
                  <IngestStatusBadge status={version.ingest_status} error={version.ingest_error} />
                  {version.warnings?.length ? (
                    <Badge
                      variant="outline"
                      className="ml-1 border-amber-600/40 bg-amber-500/10 text-amber-700 dark:text-amber-400"
                      title={version.warnings.join("\n")}
                    >
                      {version.warnings.length} quarantined
                    </Badge>
                  ) : null}
                </TableCell>
                <TableCell>
                  {version.effective_date}
                  {version.expiry_date ? ` → ${version.expiry_date}` : ""}
                </TableCell>
                <TableCell className="text-right tabular-nums">{version.chunk_count}</TableCell>
                <TableCell>{actions(doc, version)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <ChunksDialog
        versionId={chunksFor?.id ?? null}
        label={chunksFor?.label ?? ""}
        onClose={() => setChunksFor(null)}
      />
    </>
  );
}
