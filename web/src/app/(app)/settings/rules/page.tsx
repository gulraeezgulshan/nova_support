import { redirect } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { RulesTable } from "@/components/settings/rules-table";
import { NoAccess } from "@/components/no-access";
import { getCurrentUser } from "@/lib/api/server";
import { can } from "@/lib/access";

export const metadata = { title: "Rule matrix" };

export default async function RulesPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "rules")) return <NoAccess />;

  return (
    <>
      <PageHeader
        title="Complaint Resolution Rule Matrix"
        description="The Python ground truth: resolution rules per category and escalation rules that apply to every complaint. Administrators can add and edit rules."
      />
      <RulesTable canEdit={can(result.user, "rules", "edit")} />
    </>
  );
}
