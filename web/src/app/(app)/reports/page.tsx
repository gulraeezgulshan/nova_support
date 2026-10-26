import { redirect } from "next/navigation";

import { ReportsView } from "@/components/analytics/reports-view";
import { PageHeader } from "@/components/page-header";
import { NoAccess } from "@/components/no-access";
import { getCurrentUser } from "@/lib/api/server";
import { can } from "@/lib/access";

export const metadata = { title: "Reports" };

export default async function ReportsPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "reports")) return <NoAccess />;
  return (
    <>
      <PageHeader
        title="Reports"
        description="Preview a report, then export it as CSV, Excel or PDF. Filters apply to the export."
      />
      <ReportsView />
    </>
  );
}
