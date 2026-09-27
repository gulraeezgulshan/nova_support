import { redirect } from "next/navigation";

import { ImportHistory } from "@/components/imports/import-history";
import { ImportWizard } from "@/components/imports/import-wizard";
import { PageHeader } from "@/components/page-header";
import { getCurrentUser } from "@/lib/api/server";

export const metadata = { title: "Import complaints" };

export default async function ImportsPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok" || !["manager", "admin"].includes(result.user.role))
    redirect("/dashboard");
  return (
    <>
      <PageHeader
        title="Import complaints"
        description="Upload a CSV or Excel file of complaints (for example a batch from the call centre). Every row is checked first; nothing is filed until you import."
      />
      <div className="space-y-8">
        <ImportWizard />
        <ImportHistory />
      </div>
    </>
  );
}
