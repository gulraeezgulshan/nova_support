import { redirect } from "next/navigation";

import { ComplaintView } from "@/components/complaints/complaint-view";
import { NoAccess } from "@/components/no-access";
import { can } from "@/lib/access";
import { getCurrentUser } from "@/lib/api/server";
import { isStaff } from "@/lib/roles";

export default async function ComplaintPage({ params }: PageProps<"/complaints/[ref]">) {
  const { ref } = await params;
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  const { user } = result;
  const staff = isStaff(user.role);
  if (staff && !can(user, "complaints")) return <NoAccess />;
  return (
    <ComplaintView
      complaintRef={ref}
      staff={staff}
      canEdit={staff && can(user, "complaints", "edit")}
      canReview={staff && can(user, "review", "edit")}
    />
  );
}
