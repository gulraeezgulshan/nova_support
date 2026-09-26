"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Download, FileSpreadsheet, FileText } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { type AnalyticsFilters, FilterBar, filterQuery } from "@/components/analytics/filter-bar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { exportReport } from "@/lib/api/generated";
import {
  listReportsOptions,
  previewReportOptions,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ReportOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

type Format = "csv" | "xlsx" | "pdf";
const FORMATS: { value: Format; label: string; icon: typeof Download }[] = [
  { value: "csv", label: "CSV", icon: FileText },
  { value: "xlsx", label: "Excel", icon: FileSpreadsheet },
  { value: "pdf", label: "PDF", icon: Download },
];

export function ReportsView() {
  const specs = useQuery(listReportsOptions());
  const [code, setCode] = useState("complaint_intelligence");
  const [filters, setFilters] = useState<AnalyticsFilters>({});
  const [downloading, setDownloading] = useState<Format | null>(null);
  const preview = useQuery({
    ...previewReportOptions({ path: { code }, query: filterQuery(filters) }),
    placeholderData: keepPreviousData,
  });

  async function download(format: Format) {
    setDownloading(format);
    try {
      const { data, error, response } = await exportReport({
        path: { code },
        query: { ...filterQuery(filters), format },
        parseAs: "blob",
      });
      if (error || !(data instanceof Blob)) throw error;
      const disposition = response?.headers.get("Content-Disposition") ?? "";
      const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? `${code}.${format}`;
      const url = URL.createObjectURL(data);
      const link = Object.assign(document.createElement("a"), { href: url, download: name });
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(apiErrorMessage(err, "Export failed."));
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
      <nav className="space-y-1" aria-label="Reports">
        {specs.isPending ? <Skeleton className="h-64 w-full" /> : null}
        {specs.data?.map((spec) => (
          <button
            key={spec.code}
            type="button"
            onClick={() => setCode(spec.code)}
            className={cn(
              "w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors hover:bg-muted",
              spec.code === code ? "border-primary bg-muted" : "border-transparent",
            )}
          >
            <span className="font-medium">{spec.title}</span>
            <span className="block text-xs text-muted-foreground">{spec.description}</span>
          </button>
        ))}
      </nav>

      <div className="min-w-0 space-y-4">
        <FilterBar value={filters} onChange={setFilters} />
        <div className="flex flex-wrap gap-2">
          {FORMATS.map((f) => (
            <Button
              key={f.value}
              variant="outline"
              disabled={downloading !== null}
              onClick={() => download(f.value)}
            >
              <f.icon /> {downloading === f.value ? "Preparing…" : `Export ${f.label}`}
            </Button>
          ))}
        </div>
        {preview.isPending ? (
          <Skeleton className="h-96 w-full" />
        ) : preview.isError ? (
          <p className="text-sm text-destructive">{apiErrorMessage(preview.error)}</p>
        ) : (
          <ReportPreview report={preview.data} />
        )}
      </div>
    </div>
  );
}

function ReportPreview({ report }: { report: ReportOut }) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{report.title}</CardTitle>
          <CardDescription>
            {report.description} Generated {formatDateTime(report.generated_at)}.
            {report.filters.length
              ? ` Filters: ${report.filters.map((f) => `${f.label} ${f.value}`).join(", ")}.`
              : null}
          </CardDescription>
        </CardHeader>
        {report.summary.length ? (
          <CardContent>
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 xl:grid-cols-3">
              {report.summary.map((s) => (
                <div key={s.label} className="flex justify-between gap-3 border-b py-1">
                  <dt className="text-muted-foreground">{s.label}</dt>
                  <dd className="font-medium tabular-nums">{s.value ?? "—"}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        ) : null}
      </Card>

      {report.tables.map((table) => (
        <Card key={table.title} className="min-w-0">
          <CardHeader>
            <CardTitle className="text-base">{table.title}</CardTitle>
            <CardDescription>
              {table.total_rows} row{table.total_rows === 1 ? "" : "s"}
              {table.total_rows > table.rows.length
                ? ` · showing the first ${table.rows.length}; the exports contain all rows`
                : null}
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            {table.rows.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    {table.columns.map((c) => (
                      <TableHead key={c.key}>{c.header}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {table.rows.map((row, i) => (
                    <TableRow key={i}>
                      {table.columns.map((c) => (
                        <TableCell
                          key={c.key}
                          className="max-w-80 truncate"
                          title={String(row[c.key] ?? "")}
                        >
                          {String(row[c.key] ?? "") || "—"}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">No data.</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
