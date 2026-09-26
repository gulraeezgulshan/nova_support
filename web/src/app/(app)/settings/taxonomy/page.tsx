import { redirect } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { TaxonomyManager } from "@/components/settings/taxonomy-manager";
import { getCurrentUser } from "@/lib/api/server";
import { isStaff } from "@/lib/roles";

export const metadata = { title: "Taxonomy & SLAs" };

export default async function TaxonomyPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok" || !isStaff(result.user.role)) redirect("/dashboard");

  return (
    <>
      <PageHeader
        title="Taxonomy & SLAs"
        description="Configuration used by complaint classification, routing and SLA tracking. Changes apply immediately, with no redeploy."
      />
      <TaxonomyManager canManage={result.user.role === "admin"} />
    </>
  );
}
