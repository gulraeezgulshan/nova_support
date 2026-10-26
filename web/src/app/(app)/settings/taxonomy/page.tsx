import { redirect } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { TaxonomyManager } from "@/components/settings/taxonomy-manager";
import { NoAccess } from "@/components/no-access";
import { getCurrentUser } from "@/lib/api/server";
import { can } from "@/lib/access";

export const metadata = { title: "Taxonomy & SLAs" };

export default async function TaxonomyPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "taxonomy")) return <NoAccess />;

  return (
    <>
      <PageHeader
        title="Taxonomy & SLAs"
        description="Configuration used by complaint classification, routing and SLA tracking. Changes apply immediately, with no redeploy."
      />
      <TaxonomyManager canManage={can(result.user, "taxonomy", "edit")} />
    </>
  );
}
