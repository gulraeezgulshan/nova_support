"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import {
  BarList,
  ChartCard,
  ColumnChart,
  KpiCard,
  VolumeChart,
} from "@/components/analytics/charts";
import { type AnalyticsFilters, FilterBar, filterQuery } from "@/components/analytics/filter-bar";
import { TrendList } from "@/components/dashboard/admin-dashboard";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { analyticsOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import type { AnalyticsOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";

type Bucket = "day" | "week" | "month";

export function AnalyticsView() {
  const [filters, setFilters] = useState<AnalyticsFilters>({});
  const [bucket, setBucket] = useState<Bucket>("week");
  const query = useQuery({
    ...analyticsOptions({ query: { ...filterQuery(filters), bucket } }),
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
        <AnalyticsBody data={query.data} bucket={bucket} onBucket={setBucket} />
      )}
    </div>
  );
}

const num = (value: number | null | undefined, suffix = "") =>
  value == null ? "—" : `${value}${suffix}`;

function AnalyticsBody({
  data,
  bucket,
  onBucket,
}: {
  data: AnalyticsOut;
  bucket: Bucket;
  onBucket: (b: Bucket) => void;
}) {
  const o = data.overview;
  const d = data.distributions;
  return (
    <>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <KpiCard label="Complaints" value={o.total} />
        <KpiCard
          label="Escalated"
          value={o.escalated}
          hint={`${num(o.total ? Math.round((100 * o.escalated) / o.total) : null, "%")} of all`}
        />
        <KpiCard label="Repeat complaints" value={o.repeat} />
        <KpiCard label="Resolved" value={o.resolved} />
        <KpiCard label="Avg resolution" value={num(o.avg_resolution_hours, " h")} />
        <KpiCard label="SLA compliance" value={num(o.sla_compliance_pct, "%")} />
      </div>

      <ChartCard
        title="Complaint volume"
        description="Total, escalated and repeat complaints over time."
      >
        <div className="mb-3 flex justify-end">
          <Select value={bucket} onValueChange={(v) => onBucket(v as Bucket)}>
            <SelectTrigger className="w-32" aria-label="Group by">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="day">By day</SelectItem>
              <SelectItem value="week">By week</SelectItem>
              <SelectItem value="month">By month</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <VolumeChart data={data.volume} />
      </ChartCard>

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard title="By category" className="lg:col-span-2">
          <ColumnChart items={d.category ?? []} />
        </ChartCard>
        <ChartCard title="Trends" description="Emerging patterns in the last 7 days.">
          <TrendList trends={data.trends} />
        </ChartCard>
        <ChartCard title="By product line">
          <BarList items={d.product ?? []} color="var(--chart-2)" />
        </ChartCard>
        <ChartCard title="By subcategory">
          <BarList items={d.subcategory ?? []} limit={10} color="var(--chart-1)" />
        </ChartCard>
        <ChartCard title="By department">
          <BarList items={d.department ?? []} color="var(--chart-5)" />
        </ChartCard>
        <ChartCard title="By urgency">
          <BarList items={d.urgency ?? []} color="var(--chart-4)" />
        </ChartCard>
        <ChartCard title="By sentiment" description="Urgency is set by risk, not by tone.">
          <BarList items={d.sentiment ?? []} color="var(--chart-3)" />
        </ChartCard>
        <ChartCard title="Escalations by level">
          <BarList items={d.escalation_level ?? []} color="var(--chart-4)" />
        </ChartCard>
        <ChartCard title="By channel">
          <BarList items={d.channel ?? []} color="var(--chart-2)" />
        </ChartCard>
        <ChartCard title="By customer type">
          <BarList items={d.customer_type ?? []} color="var(--chart-1)" />
        </ChartCard>
        <ChartCard title="Resolution time by priority">
          {data.resolution_time.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Priority</TableHead>
                  <TableHead className="text-right">Resolved</TableHead>
                  <TableHead className="text-right">Median</TableHead>
                  <TableHead className="text-right">Within SLA</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.resolution_time.map((r) => (
                  <TableRow key={r.priority}>
                    <TableCell>{r.priority}</TableCell>
                    <TableCell className="text-right tabular-nums">{r.resolved}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {num(r.median_hours, " h")}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {num(r.within_sla_pct, "%")}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">No resolved complaints yet.</p>
          )}
        </ChartCard>
      </div>

      <ChartCard title="Department performance">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Department</TableHead>
              {[
                "Total",
                "Open",
                "Resolved",
                "Escalated",
                "Repeat",
                "At risk",
                "Breached",
                "Avg resolution",
                "SLA compliance",
              ].map((h) => (
                <TableHead key={h} className="text-right">
                  {h}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.departments.map((r) => (
              <TableRow key={r.department}>
                <TableCell>{r.label}</TableCell>
                {[r.total, r.open, r.resolved, r.escalated, r.repeat, r.at_risk, r.breached].map(
                  (v, i) => (
                    <TableCell key={i} className="text-right tabular-nums">
                      {v}
                    </TableCell>
                  ),
                )}
                <TableCell className="text-right tabular-nums">
                  {num(r.avg_resolution_hours, " h")}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {num(r.sla_compliance_pct, "%")}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ChartCard>

      <ChartCard
        title="Policy usage"
        description="Knowledge-base documents used to ground and check recommendations."
      >
        {data.policy_usage.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Document</TableHead>
                <TableHead>Versions</TableHead>
                <TableHead className="text-right">Retrieved</TableHead>
                <TableHead className="text-right">Cited by GenAI</TableHead>
                <TableHead className="text-right">Required by rules</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.policy_usage.map((r) => (
                <TableRow key={r.doc_code}>
                  <TableCell className="font-mono text-xs">{r.doc_code}</TableCell>
                  <TableCell>{r.versions || "—"}</TableCell>
                  <TableCell className="text-right tabular-nums">{r.retrieved}</TableCell>
                  <TableCell className="text-right tabular-nums">{r.cited}</TableCell>
                  <TableCell className="text-right tabular-nums">{r.required_by_rules}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="text-sm text-muted-foreground">No analysed complaints yet.</p>
        )}
      </ChartCard>
    </>
  );
}
