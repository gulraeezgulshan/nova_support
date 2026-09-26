import { redirect } from "next/navigation";

import { ComplaintView } from "@/components/complaints/complaint-view";
import { getCurrentUser } from "@/lib/api/server";
import { isStaff } from "@/lib/roles";

export default async function ComplaintPage({ params }: PageProps<"/complaints/[ref]">) {
  const { ref } = await params;
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  return <ComplaintView complaintRef={ref} staff={isStaff(result.user.role)} />;
}
