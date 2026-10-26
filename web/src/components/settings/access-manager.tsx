"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  readAccessOptions,
  readAccessQueryKey,
  updateAccessMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { AccessOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

type Level = "none" | "view" | "edit";
type Role = "agent" | "reviewer" | "manager";
type Matrix = Record<string, Record<Role, Level>>;

const ROLES: { key: Role; label: string }[] = [
  { key: "agent", label: "Support Agent" },
  { key: "reviewer", label: "Reviewer" },
  { key: "manager", label: "Support Manager" },
];

function toMatrix(data: AccessOut): Matrix {
  return Object.fromEntries(
    data.pages.map((p) => {
      const row = (data.matrix as unknown as Matrix)[p.key];
      return [p.key, { agent: row.agent, reviewer: row.reviewer, manager: row.manager }];
    }),
  );
}

function Check({
  checked,
  disabled,
  label,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  label: string;
  onChange?: (checked: boolean) => void;
}) {
  return (
    <input
      type="checkbox"
      aria-label={label}
      className="size-4 cursor-pointer accent-primary disabled:cursor-not-allowed disabled:opacity-60"
      checked={checked}
      disabled={disabled}
      onChange={(e) => onChange?.(e.target.checked)}
    />
  );
}

export function AccessManager() {
  const queryClient = useQueryClient();
  const access = useQuery(readAccessOptions());
  // Only unsaved edits live in state; otherwise the table shows the saved matrix.
  const [edits, setEdits] = useState<Matrix | null>(null);
  const save = useMutation({
    ...updateAccessMutation(),
    onSuccess: (data) => {
      toast.success("Saved. Applies within 15 seconds");
      queryClient.setQueryData(readAccessQueryKey(), data);
      setEdits(null);
    },
    onError: (err) => {
      const message = apiErrorMessage(err, "Page access was not saved.");
      toast.error(
        message.startsWith("Someone else changed")
          ? "Someone else changed the settings. Reload to see their changes."
          : message,
      );
    },
  });

  const saved = access.data ? toMatrix(access.data) : null;
  const matrix = edits ?? saved;
  const dirty = edits !== null && JSON.stringify(edits) !== JSON.stringify(saved);

  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  if (access.isPending) return <Skeleton className="h-96 w-full" />;
  if (access.isError)
    return <p className="text-sm text-destructive">{apiErrorMessage(access.error)}</p>;
  const data = access.data;
  if (!matrix || !saved) return null;

  const set = (page: string, role: Role, level: Level) =>
    setEdits({ ...matrix, [page]: { ...matrix[page], [role]: level } });
  const resetToDefaults = () => {
    if (
      !window.confirm("Put every page back to its default access? Nothing changes until you save.")
    )
      return;
    setEdits(
      Object.fromEntries(
        data.pages.map((p) => [p.key, { ...(p.default as Record<Role, Level>) }]),
      ) as Matrix,
    );
  };

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead rowSpan={2} className="align-bottom">
                Page
              </TableHead>
              {[...ROLES.map((r) => r.label), "Administrator"].map((label) => (
                <TableHead key={label} colSpan={2} className="border-l text-center">
                  {label}
                </TableHead>
              ))}
            </TableRow>
            <TableRow>
              {[...ROLES, { key: "admin", label: "Administrator" }].flatMap((r) => [
                <TableHead key={`${r.key}-view`} className="border-l text-center text-xs">
                  View
                </TableHead>,
                <TableHead key={`${r.key}-edit`} className="text-center text-xs">
                  Edit
                </TableHead>,
              ])}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.pages.map((page) => {
              const row = matrix[page.key];
              const changed = JSON.stringify(row) !== JSON.stringify(saved[page.key]);
              return (
                <TableRow key={page.key}>
                  <TableCell className="min-w-56 whitespace-normal">
                    <div className="flex items-center gap-2 font-medium">
                      {page.label}
                      {changed ? (
                        <span
                          className="size-2 rounded-full bg-amber-500"
                          aria-label="Unsaved change"
                        />
                      ) : null}
                    </div>
                    <p className="text-xs text-muted-foreground">{page.description}</p>
                  </TableCell>
                  {ROLES.map((role) => {
                    const level = row[role.key];
                    return [
                      <TableCell key={`${role.key}-view`} className="border-l text-center">
                        <Check
                          label={`${role.label} can view ${page.label}`}
                          checked={level !== "none"}
                          onChange={(on) => set(page.key, role.key, on ? "view" : "none")}
                        />
                      </TableCell>,
                      <TableCell key={`${role.key}-edit`} className="text-center">
                        {page.has_edit ? (
                          <Check
                            label={`${role.label} can edit ${page.label}`}
                            checked={level === "edit"}
                            onChange={(on) => set(page.key, role.key, on ? "edit" : "view")}
                          />
                        ) : null}
                      </TableCell>,
                    ];
                  })}
                  <TableCell className="border-l text-center">
                    <AdminLock label={`Administrator can view ${page.label}`} />
                  </TableCell>
                  <TableCell className="text-center">
                    {page.has_edit ? (
                      <AdminLock label={`Administrator can edit ${page.label}`} />
                    ) : null}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <p className="text-sm text-muted-foreground">
        Always Administrator only: Settings, Page access, changing a user&apos;s role.
      </p>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
        <p className="text-xs text-muted-foreground">
          {data.updated_at
            ? `Settings last changed by ${data.updated_by ?? "an administrator"} on ${new Date(data.updated_at).toLocaleString()}`
            : "Using the default access."}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={resetToDefaults}>
            Reset to defaults
          </Button>
          <Button variant="ghost" disabled={!dirty} onClick={() => setEdits(null)}>
            Discard
          </Button>
          <Button
            disabled={!dirty || save.isPending}
            onClick={() => save.mutate({ body: { matrix, version: data.version } })}
          >
            Save
          </Button>
        </div>
      </div>
    </div>
  );
}

function AdminLock({ label }: { label: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={cn("inline-flex items-center gap-1")}>
          <Check label={label} checked disabled />
          <Lock className="size-3 text-muted-foreground" aria-hidden />
        </span>
      </TooltipTrigger>
      <TooltipContent>Administrators always have full access</TooltipContent>
    </Tooltip>
  );
}
