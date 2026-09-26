import { Plus } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { ComplaintsTable } from "@/components/complaints/complaints-table";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { getCurrentUser } from "@/lib/api/server";
import { isStaff } from "@/lib/roles";

export const metadata = { title: "Complaints" };

export default async function ComplaintsPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  const staff = isStaff(result.user.role);

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
          <Button asChild>
            <Link href="/complaints/new">
              <Plus /> {staff ? "Log a complaint" : "New complaint"}
            </Link>
          </Button>
        }
      />
      <ComplaintsTable staff={staff} />
    </>
  );
}
