"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  listDocumentsQueryKey,
  listDocumentTypesOptions,
  uploadDocumentMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import { apiErrorMessage } from "@/lib/api/errors";

const ACCEPT = ".pdf,.docx,.txt,.md";
const FROM_DOCUMENT = "__from_document__";

type Fields = {
  doc_code: string;
  title: string;
  doc_type: string;
  version: string;
  effective_date: string;
  expiry_date: string;
};
const EMPTY: Fields = {
  doc_code: "",
  title: "",
  doc_type: FROM_DOCUMENT,
  version: "",
  effective_date: "",
  expiry_date: "",
};

export function UploadDialog() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [fields, setFields] = useState<Fields>(EMPTY);
  const [activate, setActivate] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const types = useQuery({ ...listDocumentTypesOptions(), enabled: open });

  const upload = useMutation({
    ...uploadDocumentMutation(),
    onSuccess: (version) => {
      toast.success(`Version ${version.version} uploaded`, {
        description: "Parsing, chunking and embedding run in the background.",
      });
      queryClient.invalidateQueries({ queryKey: listDocumentsQueryKey() });
      setOpen(false);
      setFile(null);
      setFields(EMPTY);
    },
    onError: (err) => setError(apiErrorMessage(err, "Upload failed.")),
  });

  function set<K extends keyof Fields>(key: K, value: string) {
    setFields((current) => ({ ...current, [key]: value }));
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setError(null);
    const optional = Object.fromEntries(
      Object.entries(fields).filter(([, v]) => v.trim() !== "" && v !== FROM_DOCUMENT),
    );
    upload.mutate({ body: { file, activate, ...optional } });
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Upload /> Upload document
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Upload a knowledge-base document</DialogTitle>
            <DialogDescription>
              PDF, DOCX, TXT or Markdown. Leave fields blank to read them from the document header
              (lines such as “Document ID: DEL-POL-04”).
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="file">File</Label>
            <Input
              id="file"
              type="file"
              accept={ACCEPT}
              required
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="doc_code">Document ID</Label>
              <Input
                id="doc_code"
                placeholder="From document"
                value={fields.doc_code}
                onChange={(e) => set("doc_code", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="version">Version</Label>
              <Input
                id="version"
                placeholder="From document"
                value={fields.version}
                onChange={(e) => set("version", e.target.value)}
              />
            </div>
            <div className="col-span-2 space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                placeholder="From document"
                value={fields.title}
                onChange={(e) => set("title", e.target.value)}
              />
            </div>
            <div className="col-span-2 space-y-2">
              <Label>Document category</Label>
              <Select value={fields.doc_type} onValueChange={(v) => set("doc_type", v)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={FROM_DOCUMENT}>From document</SelectItem>
                  {types.data?.map((t) => (
                    <SelectItem key={t.code} value={t.code}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="effective_date">Effective date</Label>
              <Input
                id="effective_date"
                type="date"
                value={fields.effective_date}
                onChange={(e) => set("effective_date", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="expiry_date">Expiry date</Label>
              <Input
                id="expiry_date"
                type="date"
                value={fields.expiry_date}
                onChange={(e) => set("expiry_date", e.target.value)}
              />
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <Label htmlFor="activate">Activate when processed</Label>
              <p className="text-xs text-muted-foreground">
                Replaces the current active version of this document.
              </p>
            </div>
            <Switch id="activate" checked={activate} onCheckedChange={setActivate} />
          </div>

          {error ? (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          ) : null}

          <DialogFooter>
            <Button type="submit" disabled={!file || upload.isPending}>
              {upload.isPending ? "Uploading…" : "Upload"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
