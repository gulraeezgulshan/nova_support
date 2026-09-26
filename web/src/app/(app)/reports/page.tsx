import { redirect } from "next/navigation";

import { ReportsView } from "@/components/analytics/reports-view";
import { PageHeader } from "@/components/page-header";
import { getCurrentUser } from "@/lib/api/server";

export const metadata = { title: "Reports" };

export default async function ReportsPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok" || !["reviewer", "manager", "admin"].includes(result.user.role)) {
    redirect("/dashboard");
  }
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
