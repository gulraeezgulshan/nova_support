import { redirect } from "next/navigation";

import { AnalyticsView } from "@/components/analytics/analytics-view";
import { PageHeader } from "@/components/page-header";
import { getCurrentUser } from "@/lib/api/server";

export const metadata = { title: "Analytics" };

export default async function AnalyticsPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok" || !["reviewer", "manager", "admin"].includes(result.user.role)) {
    redirect("/dashboard");
  }
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
