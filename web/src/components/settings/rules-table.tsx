"use client";

import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { exportRules } from "@/lib/api/generated";
import { listRulesOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import { apiErrorMessage } from "@/lib/api/errors";

import { PriorityBadge } from "../complaints/badges";

export function RulesTable() {
  const rules = useQuery(listRulesOptions());
  const [filter, setFilter] = useState("");
  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return (rules.data ?? []).filter((r) =>
      needle
        ? [r.rule_id, r.category, r.subcategory, r.condition, r.description]
            .join(" ")
            .toLowerCase()
            .includes(needle)
        : true,
    );
  }, [rules.data, filter]);

  async function download() {
    const { data } = await exportRules({ parseAs: "text" });
    const url = URL.createObjectURL(new Blob([data as string], { type: "text/csv" }));
    const link = Object.assign(document.createElement("a"), {
      href: url,
      download: "rule_matrix.csv",
    });
    link.click();
    URL.revokeObjectURL(url);
  }

  if (rules.isPending) return <Skeleton className="h-96" />;
  if (rules.isError)
    return <p className="text-sm text-destructive">{apiErrorMessage(rules.error)}</p>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Input
          className="w-72"
          placeholder="Filter by ID, category or condition"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <Button variant="outline" onClick={download}>
          <Download /> Export CSV
        </Button>
        <span className="self-center text-sm text-muted-foreground">
          {visible.length} of {rules.data.length} rules
        </span>
      </div>
      <div className="rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Rule</TableHead>
              <TableHead>Applies to</TableHead>
              <TableHead>Condition</TableHead>
              <TableHead>Outcome</TableHead>
              <TableHead>Required / prohibited</TableHead>
              <TableHead>Policy</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visible.map((r) => (
              <TableRow key={r.rule_id} className={r.is_active ? "" : "opacity-50"}>
                <TableCell className="align-top">
                  <div className="font-mono text-xs">{r.rule_id}</div>
                  <Badge variant={r.rule_type === "escalation" ? "destructive" : "secondary"}>
                    {r.rule_type}
                  </Badge>
                  <div className="text-[11px] text-muted-foreground">v{r.version}</div>
                </TableCell>
                <TableCell className="max-w-56 align-top text-xs">
                  {r.category
                    ? `${r.category}${r.subcategory ? ` / ${r.subcategory}` : ""}`
                    : "Any complaint"}
                  <p className="mt-1 text-muted-foreground">{r.description}</p>
                </TableCell>
                <TableCell className="max-w-56 align-top">
                  <code className="whitespace-pre-wrap text-xs">{r.condition || "always"}</code>
                </TableCell>
                <TableCell className="align-top text-xs">
                  <div className="flex items-center gap-1">
                    <PriorityBadge priority={r.priority} /> {r.urgency}
                  </div>
                  <div>{r.department ?? "keep department"}</div>
                  {r.escalation_level ? <div>Escalation L{r.escalation_level}</div> : null}
                </TableCell>
                <TableCell className="max-w-64 align-top text-[11px]">
                  <div className="text-emerald-700 dark:text-emerald-400">
                    {r.required_actions.join(", ")}
                  </div>
                  <div className="text-red-700 dark:text-red-400">
                    {r.prohibited_actions.join(", ")}
                  </div>
                </TableCell>
                <TableCell className="align-top font-mono text-[11px]">
                  {r.policy_refs.join(" ")}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
