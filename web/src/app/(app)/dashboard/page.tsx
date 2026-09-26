import { Plus } from "lucide-react";
import Link from "next/link";

import { ComplaintsTable } from "@/components/complaints/complaints-table";
import { AdminDashboard } from "@/components/dashboard/admin-dashboard";
import { AgentDashboard } from "@/components/dashboard/agent-dashboard";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { getCurrentUser } from "@/lib/api/server";
import { ROLE_LABELS } from "@/lib/roles";

export const metadata = { title: "Dashboard" };

export default async function DashboardPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") return null; // handled by the layout
  const { user } = result;
  const firstName = user.full_name?.split(" ")[0];
  const greeting = firstName ? `Welcome, ${firstName}` : "Welcome";

  if (user.role === "customer") {
    return (
      <>
        <PageHeader
          title={greeting}
          description="Track your complaints. We acknowledge every complaint immediately."
          actions={
            <Button asChild>
              <Link href="/complaints/new">
                <Plus /> Submit a complaint
              </Link>
            </Button>
          }
        />
        <ComplaintsTable staff={false} />
      </>
    );
  }

  if (user.role === "agent") {
    return (
      <>
        <PageHeader
          title={greeting}
          description="Your department's open complaints with the AI recommendation, validation result and warnings."
        />
        <AgentDashboard ownDepartment={user.department?.name} />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Complaint operations"
        description={`Signed in as ${ROLE_LABELS[user.role]}. Organisation-wide view of volume, risk, SLA and validation.`}
        actions={
          <>
            <Button asChild variant="outline">
              <Link href="/analytics">Analytics</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/reports">Reports</Link>
            </Button>
          </>
        }
      />
      <AdminDashboard />
    </>
  );
}
