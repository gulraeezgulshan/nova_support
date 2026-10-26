import { redirect } from "next/navigation";

import { ComplaintForm } from "@/components/complaints/complaint-form";
import { PageHeader } from "@/components/page-header";
import { NoAccess } from "@/components/no-access";
import { can } from "@/lib/access";
import { getCurrentUser } from "@/lib/api/server";
import { isStaff } from "@/lib/roles";

export const metadata = { title: "New complaint" };

export default async function NewComplaintPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  const staff = isStaff(result.user.role);
  if (staff && !can(result.user, "complaints", "edit")) return <NoAccess />;

  return (
    <>
      <PageHeader
        title={staff ? "Log a complaint for a customer" : "Submit a complaint"}
        description="We will acknowledge it straight away and keep you updated here."
      />
      <ComplaintForm staff={staff} />
    </>
  );
}
