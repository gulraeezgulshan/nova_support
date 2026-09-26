import { redirect } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { RulesTable } from "@/components/settings/rules-table";
import { getCurrentUser } from "@/lib/api/server";
import { isStaff } from "@/lib/roles";

export const metadata = { title: "Rule matrix" };

export default async function RulesPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok" || !isStaff(result.user.role)) redirect("/dashboard");

  return (
    <>
      <PageHeader
        title="Complaint Resolution Rule Matrix"
        description="The Python ground truth: resolution rules per category and escalation rules that apply to every complaint."
      />
      <RulesTable />
    </>
  );
}
