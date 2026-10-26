import { redirect } from "next/navigation";

import { AnalyticsView } from "@/components/analytics/analytics-view";
import { PageHeader } from "@/components/page-header";
import { NoAccess } from "@/components/no-access";
import { getCurrentUser } from "@/lib/api/server";
import { can } from "@/lib/access";

export const metadata = { title: "Analytics" };

export default async function AnalyticsPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "analytics")) return <NoAccess />;
  return (
    <>
      <PageHeader
        title="Complaint analytics"
        description="Volume, categories, products, departments, urgency, sentiment, escalations, resolution time, repeats and trends."
      />
      <AnalyticsView />
    </>
  );
}
