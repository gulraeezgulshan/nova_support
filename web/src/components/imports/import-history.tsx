"use client";

import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listImportsOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import { importResult } from "@/lib/api/generated/sdk.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { saveBlob } from "@/lib/download";
import { formatDateTime } from "@/lib/format";

export async function downloadResult(batchId: string, filename: string) {
  try {
    const { data } = await importResult({
      path: { batch_id: batchId },
      parseAs: "blob",
      throwOnError: true,
    });
    saveBlob(data as unknown as Blob, `${filename.replace(/\.[^.]+$/, "")}-result.csv`);
  } catch (err) {
    toast.error(apiErrorMessage(err, "Download failed."));
  }
}

export function ImportHistory() {
  const imports = useQuery({ ...listImportsOptions(), refetchInterval: 10_000 });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent imports</CardTitle>
      </CardHeader>
      <CardContent>
        {imports.isPending ? (
          <Skeleton className="h-24" />
        ) : imports.isError ? (
          <p className="text-sm text-destructive">{apiErrorMessage(imports.error)}</p>
        ) : !imports.data.length ? (
          <p className="text-sm text-muted-foreground">No imports yet.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File</TableHead>
                <TableHead>Uploaded</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Created</TableHead>
                <TableHead className="text-right">Skipped</TableHead>
                <TableHead className="text-right">Failed</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {imports.data.map((b) => (
                <TableRow key={b.id}>
                  <TableCell className="max-w-48 truncate text-sm">{b.filename}</TableCell>
                  <TableCell className="text-xs whitespace-nowrap">
                    {formatDateTime(b.created_at)}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        b.status === "done"
                          ? "default"
                          : b.status === "failed"
                            ? "destructive"
                            : "secondary"
                      }
                    >
                      {b.status === "previewed" ? "Not imported" : b.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{b.created}</TableCell>
                  <TableCell className="text-right tabular-nums">{b.skipped}</TableCell>
                  <TableCell className="text-right tabular-nums">{b.failed}</TableCell>
                  <TableCell className="text-right">
                    {b.status === "done" ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => void downloadResult(b.id, b.filename)}
                      >
                        <Download /> Result
                      </Button>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
