"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { TrendingUp } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { BarList, ChartCard, ColumnChart, KpiCard } from "@/components/analytics/charts";
import { type AnalyticsFilters, FilterBar, filterQuery } from "@/components/analytics/filter-bar";
import { PriorityBadge, SlaBadge } from "@/components/complaints/badges";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { adminDashboardOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import type { AdminDashboardOut, TrendOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { formatDateTime, humanize } from "@/lib/format";

export function AdminDashboard() {
  const [filters, setFilters] = useState<AnalyticsFilters>({});
  const query = useQuery({
    ...adminDashboardOptions({ query: filterQuery(filters) }),
    placeholderData: keepPreviousData,
  });

  return (
    <div className="space-y-6">
      <FilterBar value={filters} onChange={setFilters} />
      {query.isPending ? (
        <Skeleton className="h-96 w-full" />
      ) : query.isError ? (
        <p className="text-sm text-destructive">{apiErrorMessage(query.error)}</p>
      ) : (
        <DashboardBody data={query.data} />
      )}
    </div>
  );
}

function DashboardBody({ data }: { data: AdminDashboardOut }) {
  const o = data.overview;
  const d = data.distributions;
  return (
    <>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <KpiCard label="Total complaints" value={o.total} hint={`${o.open} open`} />
        <KpiCard
          label="Escalated"
          value={o.escalated}
          hint={`${o.open_escalated} still open`}
          tone={o.open_escalated ? "warning" : undefined}
        />
        <KpiCard
          label="SLA at risk"
          value={o.sla_at_risk}
          tone={o.sla_at_risk ? "warning" : undefined}
        />
        <KpiCard
          label="SLA breached"
          value={o.sla_breached}
          tone={o.sla_breached ? "danger" : undefined}
        />
        <KpiCard
          label="SLA compliance"
          value={o.sla_compliance_pct != null ? `${o.sla_compliance_pct}%` : "—"}
          hint={`${o.sla_met} met · ${o.sla_missed} missed`}
        />
        <KpiCard
          label="GenAI/Python mismatches"
          value={o.mismatches}
          hint={`of ${o.analysed} analysed`}
          tone={o.mismatches ? "warning" : undefined}
        />
        <KpiCard label="Manual review" value={o.open_reviews} hint="open cases" />
        <KpiCard
          label="Avg resolution"
          value={o.avg_resolution_hours != null ? `${o.avg_resolution_hours} h` : "—"}
          hint={`${o.resolved} resolved`}
        />
      </div>
      {o.unclassified ? (
        <p className="text-xs text-muted-foreground">
          {o.unclassified} complaint(s) are waiting for analysis and appear as
          &ldquo;Unclassified&rdquo;.
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard title="Category distribution" className="lg:col-span-2">
          <ColumnChart items={d.category ?? []} />
        </ChartCard>
        <ChartCard title="Department distribution">
          <BarList items={d.department ?? []} limit={8} color="var(--chart-2)" />
        </ChartCard>
        <ChartCard title="Priority levels">
          <BarList items={d.priority ?? []} color="var(--chart-4)" />
        </ChartCard>
        <ChartCard title="Escalations by level">
          <BarList
            items={(d.escalation_level ?? []).filter((i) => i.key !== "0")}
            color="var(--chart-3)"
          />
        </ChartCard>
        <ChartCard title="Resolution status">
          <BarList items={d.status ?? []} color="var(--chart-5)" />
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard
          title="SLA risks"
          description="Open complaints at risk of missing, or past, their deadline."
          className="lg:col-span-2"
        >
          <SlaRiskTable rows={data.sla_risks} />
        </ChartCard>
        <ChartCard title="Trends" description="Last 7 days compared with the 7 days before.">
          <TrendList trends={data.trends} />
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard
          title="GenAI vs Python agreement"
          description={`${data.agreement.compared} analysed complaints`}
        >
          <BarList
            items={Object.entries(data.agreement.agreement_pct).map(([field, pct]) => ({
              key: field,
              label: humanize(field),
              count: pct ?? 0,
              pct: null,
            }))}
            color="var(--chart-2)"
          />
          <p className="mt-3 text-xs text-muted-foreground">
            Share of complaints where both agree (%).
          </p>
        </ChartCard>
        <ChartCard title="Validation outcome">
          <BarList items={d.verification ?? []} color="var(--chart-1)" />
        </ChartCard>
        <ChartCard
          title="Manual-review cases"
          description={`${data.reviews.open} open · ${data.reviews.resolved} resolved`}
        >
          {data.reviews.top_reasons.length ? (
            <ul className="space-y-2 text-sm">
              {data.reviews.top_reasons.slice(0, 6).map((r) => (
                <li key={r.reason} className="flex justify-between gap-3">
                  <span className="truncate" title={r.reason}>
                    {r.reason}
                  </span>
                  <span className="tabular-nums text-muted-foreground">{r.count}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No review cases.</p>
          )}
          <Link
            href="/review"
            className="mt-3 inline-block text-sm underline-offset-4 hover:underline"
          >
            Open review queue
          </Link>
        </ChartCard>
      </div>
    </>
  );
}

export function SlaRiskTable({ rows }: { rows: AdminDashboardOut["sla_risks"] }) {
  if (!rows.length) return <p className="text-sm text-muted-foreground">No SLA risks.</p>;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Complaint</TableHead>
          <TableHead>Priority</TableHead>
          <TableHead>Department</TableHead>
          <TableHead>Due</TableHead>
          <TableHead>SLA</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.complaint_ref}>
            <TableCell className="font-mono text-xs">
              <Link className="hover:underline" href={`/complaints/${r.complaint_ref}`}>
                {r.complaint_ref}
              </Link>
            </TableCell>
            <TableCell>
              <PriorityBadge priority={r.priority} />
            </TableCell>
            <TableCell>{humanize(r.department_code)}</TableCell>
            <TableCell className="whitespace-nowrap text-muted-foreground">
              {formatDateTime(r.resolution_due_at)}
            </TableCell>
            <TableCell>
              <SlaBadge status={r.sla_status} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function TrendList({ trends }: { trends: TrendOut[] }) {
  if (!trends.length) return <p className="text-sm text-muted-foreground">No emerging trends.</p>;
  return (
    <ul className="space-y-3">
      {trends.map((t) => (
        <li key={`${t.kind}-${t.key}`} className="flex gap-2 text-sm">
          <TrendingUp className="mt-0.5 size-4 shrink-0 text-amber-600" />
          <div>
            <p className="font-medium">{t.label}</p>
            <p className="text-xs text-muted-foreground">{t.message}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
