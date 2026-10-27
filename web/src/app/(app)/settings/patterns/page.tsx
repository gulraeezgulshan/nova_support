import { redirect } from "next/navigation";

import { NoAccess } from "@/components/no-access";
import { PageHeader } from "@/components/page-header";
import { PatternsManager } from "@/components/settings/patterns-manager";
import { can } from "@/lib/access";
import { getCurrentUser } from "@/lib/api/server";

export const metadata = { title: "Patterns" };

export default async function PatternsPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "settings")) return <NoAccess />;
  return (
    <>
      <PageHeader
        title="Patterns"
        description="Risk-signal words, classifier phrases and promise wording. Test a change before saving; it applies within about 15 seconds."
      />
      <PatternsManager />
    </>
  );
}
