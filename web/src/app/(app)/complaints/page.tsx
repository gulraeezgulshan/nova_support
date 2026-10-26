import { Plus } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { ComplaintsTable } from "@/components/complaints/complaints-table";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { NoAccess } from "@/components/no-access";
import { can } from "@/lib/access";
import { getCurrentUser } from "@/lib/api/server";
import { isStaff } from "@/lib/roles";

export const metadata = { title: "Complaints" };

export default async function ComplaintsPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  const staff = isStaff(result.user.role);
  if (staff && !can(result.user, "complaints")) return <NoAccess />;
  const canLog = !staff || can(result.user, "complaints", "edit");

  return (
    <>
      <PageHeader
        title={staff ? "Complaint queue" : "My complaints"}
        description={
          staff
            ? "All complaints with their AI classification. Flagged items need manual review."
            : "Track the status of complaints you have submitted."
        }
        actions={
          canLog ? (
            <Button asChild>
              <Link href="/complaints/new">
                <Plus /> {staff ? "Log a complaint" : "New complaint"}
              </Link>
            </Button>
          ) : undefined
        }
      />
      <ComplaintsTable staff={staff} />
    </>
  );
}
