"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, Paperclip, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  deleteComplaintAttachmentMutation,
  listComplaintAttachmentsOptions,
  listComplaintAttachmentsQueryKey,
  uploadComplaintAttachmentMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import { downloadComplaintAttachment } from "@/lib/api/generated/sdk.gen";
import type { AttachmentOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { formatDateTime } from "@/lib/format";

export const MAX_ATTACHMENTS = 5;
export const MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024;
export const ACCEPTED_TYPES = "image/jpeg,image/png,image/webp,application/pdf";
const SOURCES: Record<string, string> = { email: "E-mail", customer: "Customer", staff: "Staff" };

async function fetchBlob(complaintRef: string, attachmentId: string): Promise<Blob> {
  const { data } = await downloadComplaintAttachment({
    path: { ref: complaintRef, attachment_id: attachmentId },
    parseAs: "blob",
    throwOnError: true,
  });
  return data as unknown as Blob;
}

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Photo preview fetched with the user's session (files are never public links). */
function Thumbnail({
  complaintRef,
  attachment,
}: {
  complaintRef: string;
  attachment: AttachmentOut;
}) {
  const blob = useQuery({
    queryKey: ["attachment-blob", attachment.id],
    queryFn: () => fetchBlob(complaintRef, attachment.id),
    enabled: attachment.media_type.startsWith("image/"),
    staleTime: Infinity,
  });
  const url = useMemo(() => (blob.data ? URL.createObjectURL(blob.data) : null), [blob.data]);
  useEffect(() => () => (url ? URL.revokeObjectURL(url) : undefined), [url]);
  if (!attachment.media_type.startsWith("image/"))
    return (
      <div className="flex aspect-square items-center justify-center rounded-lg bg-muted">
        <FileText className="size-8 text-muted-foreground" />
      </div>
    );
  if (!url) return <Skeleton className="aspect-square rounded-lg" />;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={url} alt={attachment.filename} className="aspect-square rounded-lg object-cover" />
  );
}

/** Photos and PDFs the customer or staff attached to a complaint. */
export function SupportingDocuments({
  complaintRef,
  staff,
}: {
  complaintRef: string;
  staff: boolean;
}) {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const attachments = useQuery(listComplaintAttachmentsOptions({ path: { ref: complaintRef } }));
  const refresh = () =>
    queryClient.invalidateQueries({
      queryKey: listComplaintAttachmentsQueryKey({ path: { ref: complaintRef } }),
    });
  const onError = (err: unknown) => toast.error(apiErrorMessage(err, "That file was not added."));
  const upload = useMutation({ ...uploadComplaintAttachmentMutation(), onError });
  const remove = useMutation({
    ...deleteComplaintAttachmentMutation(),
    onSuccess: refresh,
    onError,
  });
  const items = attachments.data ?? [];

  async function add(files: FileList) {
    const chosen = Array.from(files).slice(0, Math.max(MAX_ATTACHMENTS - items.length, 0));
    if (!chosen.length) {
      toast.error(`A complaint can have at most ${MAX_ATTACHMENTS} documents.`);
      return;
    }
    for (const file of chosen) {
      try {
        await upload.mutateAsync({ path: { ref: complaintRef }, body: { file } });
      } catch {
        break; // onError already explained why
      }
    }
    refresh();
  }

  async function download(attachment: AttachmentOut) {
    try {
      const url = URL.createObjectURL(await fetchBlob(complaintRef, attachment.id));
      const link = document.createElement("a");
      link.href = url;
      link.download = attachment.filename;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      toast.error(apiErrorMessage(err, "Download failed."));
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle>
          Supporting documents{" "}
          <span className="font-normal text-muted-foreground">
            ({items.length}/{MAX_ATTACHMENTS})
          </span>
        </CardTitle>
        <Button
          size="sm"
          variant="outline"
          disabled={upload.isPending || items.length >= MAX_ATTACHMENTS}
          onClick={() => input.current?.click()}
        >
          <Paperclip /> {upload.isPending ? "Uploading…" : "Add file"}
        </Button>
        <input
          ref={input}
          type="file"
          accept={ACCEPTED_TYPES}
          multiple
          hidden
          onChange={(event) => {
            if (event.target.files?.length) void add(event.target.files);
            event.target.value = "";
          }}
        />
      </CardHeader>
      <CardContent>
        {attachments.isPending ? (
          <Skeleton className="h-24" />
        ) : items.length ? (
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {items.map((a) => (
              <li key={a.id} className="space-y-1.5">
                <Thumbnail complaintRef={complaintRef} attachment={a} />
                <p className="truncate text-xs font-medium" title={a.filename}>
                  {a.filename}
                </p>
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Badge variant="outline" className="px-1.5 py-0 text-[10px]">
                    {SOURCES[a.source] ?? a.source}
                  </Badge>
                  {formatSize(a.size_bytes)}
                </div>
                <p className="text-[11px] text-muted-foreground">{formatDateTime(a.created_at)}</p>
                <div className="flex gap-1">
                  <Button
                    size="icon"
                    variant="ghost"
                    className="size-7"
                    aria-label={`Download ${a.filename}`}
                    onClick={() => void download(a)}
                  >
                    <Download />
                  </Button>
                  {staff ? (
                    <Button
                      size="icon"
                      variant="ghost"
                      className="size-7"
                      aria-label={`Remove ${a.filename}`}
                      disabled={remove.isPending}
                      onClick={() => {
                        if (window.confirm(`Remove ${a.filename}?`))
                          remove.mutate({ path: { ref: complaintRef, attachment_id: a.id } });
                      }}
                    >
                      <Trash2 />
                    </Button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            No documents yet. Photos (JPG, PNG, WebP) and PDFs up to 5 MB help us resolve the
            complaint faster.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
