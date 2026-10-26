import { redirect } from "next/navigation";

import { ImportHistory } from "@/components/imports/import-history";
import { ImportWizard } from "@/components/imports/import-wizard";
import { PageHeader } from "@/components/page-header";
import { NoAccess } from "@/components/no-access";
import { getCurrentUser } from "@/lib/api/server";
import { can } from "@/lib/access";

export const metadata = { title: "Import complaints" };

export default async function ImportsPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "imports")) return <NoAccess />;
  return (
    <>
      <PageHeader
        title="Import complaints"
        description="Upload a CSV or Excel file of complaints (for example a batch from the call centre). Every row is checked first; nothing is filed until you import."
      />
      <div className="space-y-8">
        {can(result.user, "imports", "edit") ? <ImportWizard /> : null}
        <ImportHistory />
      </div>
    </>
  );
}
