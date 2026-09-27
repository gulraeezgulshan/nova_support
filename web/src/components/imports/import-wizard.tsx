"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Download, FileSpreadsheet, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  getImportOptions,
  listImportsQueryKey,
  previewImportMutation,
  runImportMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import { importTemplateCsv, importTemplateXlsx } from "@/lib/api/generated/sdk.gen";
import type { ImportPreviewOut, ImportRowOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { saveBlob } from "@/lib/download";

import { downloadResult } from "./import-history";

const STATUS: Record<string, { label: string; variant: "default" | "secondary" | "destructive" }> =
  {
    ready: { label: "Ready", variant: "default" },
    warning: { label: "Warning", variant: "secondary" },
    error: { label: "Error", variant: "destructive" },
  };

async function downloadTemplate(kind: "csv" | "xlsx") {
  try {
    const call = kind === "csv" ? importTemplateCsv : importTemplateXlsx;
    const { data } = await call({ parseAs: "blob", throwOnError: true });
    saveBlob(data as unknown as Blob, `complaints-template.${kind}`);
  } catch (err) {
    toast.error(apiErrorMessage(err, "Download failed."));
  }
}

function RowsTable({ rows }: { rows: ImportRowOut[] }) {
  const [problemsOnly, setProblemsOnly] = useState(false);
  const shown = problemsOnly ? rows.filter((r) => r.status !== "ready") : rows;
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Button
          size="sm"
          variant={problemsOnly ? "outline" : "secondary"}
          onClick={() => setProblemsOnly(false)}
        >
          All rows
        </Button>
        <Button
          size="sm"
          variant={problemsOnly ? "secondary" : "outline"}
          onClick={() => setProblemsOnly(true)}
        >
          Problems only
        </Button>
      </div>
      <div className="max-h-[28rem] overflow-auto rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16">Row</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Notes</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.map((r) => (
              <TableRow key={r.row}>
                <TableCell className="tabular-nums">{r.row}</TableCell>
                <TableCell className="text-sm">{r.values.customer_email ?? "—"}</TableCell>
                <TableCell className="max-w-56 truncate text-sm">{r.values.title ?? "—"}</TableCell>
                <TableCell>
                  <Badge variant={STATUS[r.result === "failed" ? "error" : r.status].variant}>
                    {r.result === "created"
                      ? r.reference
                      : r.result === "failed"
                        ? "Failed"
                        : STATUS[r.status].label}
                  </Badge>
                </TableCell>
                <TableCell className="max-w-md text-xs whitespace-normal text-muted-foreground">
                  {r.reason ?? r.messages.join(" ")}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

/** Upload → preview every row → import the good ones → download the result. */
export function ImportWizard() {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<ImportPreviewOut | null>(null);
  const [started, setStarted] = useState(false);
  const refreshHistory = () => queryClient.invalidateQueries({ queryKey: listImportsQueryKey() });
  const check = useMutation({
    ...previewImportMutation(),
    onSuccess: (out) => {
      setPreview(out);
      setStarted(false);
      refreshHistory();
    },
    onError: (err) => toast.error(apiErrorMessage(err, "The file could not be read.")),
  });
  const run = useMutation({
    ...runImportMutation(),
    onSuccess: () => {
      setStarted(true);
      refreshHistory();
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });
  const progress = useQuery({
    ...getImportOptions({ path: { batch_id: preview?.id ?? "" } }),
    enabled: Boolean(preview && started),
    refetchInterval: (query) =>
      ["done", "failed"].includes(query.state.data?.status ?? "") ? false : 2000,
  });
  const done = progress.data?.status === "done";
  const crashed = progress.data?.status === "failed";
  const counts = preview
    ? {
        ready: preview.rows.filter((r) => r.status === "ready").length,
        warning: preview.rows.filter((r) => r.status === "warning").length,
        error: preview.rows.filter((r) => r.status === "error").length,
      }
    : null;
  const importable = counts ? counts.ready + counts.warning : 0;

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
        <CardTitle>Upload a file</CardTitle>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => void downloadTemplate("csv")}>
            <Download /> CSV template
          </Button>
          <Button size="sm" variant="outline" onClick={() => void downloadTemplate("xlsx")}>
            <Download /> Excel template
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <button
          type="button"
          onClick={() => input.current?.click()}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            const file = event.dataTransfer.files[0];
            if (file) check.mutate({ body: { file } });
          }}
          className="flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed p-8 text-center transition-colors hover:bg-muted/50"
        >
          {check.isPending ? (
            <FileSpreadsheet className="size-8 animate-pulse text-muted-foreground" />
          ) : (
            <Upload className="size-8 text-muted-foreground" />
          )}
          <p className="font-medium">
            {check.isPending
              ? "Checking every row…"
              : "Drop a CSV or .xlsx file, or click to choose"}
          </p>
          <p className="text-xs text-muted-foreground">
            Up to 1,000 rows and 5 MB. Required columns: customer_email, title, description.
          </p>
        </button>
        <input
          ref={input}
          type="file"
          accept=".csv,.xlsx"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) check.mutate({ body: { file } });
            event.target.value = "";
          }}
        />

        {preview && counts ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">{preview.filename}</span>
              <Badge>{counts.ready} ready</Badge>
              <Badge variant="secondary">{counts.warning} with warnings</Badge>
              <Badge variant="destructive">{counts.error} with errors</Badge>
              {preview.unknown_columns.length ? (
                <span className="text-xs text-muted-foreground">
                  Ignored columns: {preview.unknown_columns.join(", ")}
                </span>
              ) : null}
            </div>
            {preview.previously_imported ? (
              <Alert>
                <AlertTriangle />
                <AlertTitle>This exact file was imported before</AlertTitle>
                <AlertDescription>
                  Rows already on file are marked as duplicates and will be skipped.
                </AlertDescription>
              </Alert>
            ) : null}
            {crashed ? (
              <Alert variant="destructive">
                <AlertTriangle />
                <AlertTitle>The import stopped</AlertTitle>
                <AlertDescription>
                  Something went wrong on the server. Complaints already created are kept; download
                  the result from Recent imports once it is available, or upload the file again —
                  rows already on file will be skipped as duplicates.
                </AlertDescription>
              </Alert>
            ) : null}
            {done && progress.data ? (
              <Alert>
                <CheckCircle2 />
                <AlertTitle>Import finished</AlertTitle>
                <AlertDescription>
                  {progress.data.created} complaints created, {progress.data.skipped} skipped,{" "}
                  {progress.data.failed} failed. Each new complaint is being analysed.
                </AlertDescription>
              </Alert>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {done ? (
                <Button onClick={() => void downloadResult(preview.id, preview.filename)}>
                  <Download /> Download result
                </Button>
              ) : (
                <Button
                  disabled={!importable || started || run.isPending}
                  onClick={() => run.mutate({ path: { batch_id: preview.id } })}
                >
                  {started
                    ? "Importing…"
                    : `Import ${importable} complaint${importable === 1 ? "" : "s"}`}
                </Button>
              )}
              <Button variant="ghost" onClick={() => setPreview(null)}>
                Start again
              </Button>
            </div>
            <RowsTable rows={done && progress.data ? progress.data.rows : preview.rows} />
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
