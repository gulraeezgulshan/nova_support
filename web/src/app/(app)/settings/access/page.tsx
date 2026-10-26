import { redirect } from "next/navigation";

import { NoAccess } from "@/components/no-access";
import { PageHeader } from "@/components/page-header";
import { AccessManager } from "@/components/settings/access-manager";
import { can } from "@/lib/access";
import { getCurrentUser } from "@/lib/api/server";

export const metadata = { title: "Page access" };

export default async function PageAccessPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "access")) return <NoAccess />;
  return (
    <>
      <PageHeader
        title="Page access"
        description="Choose which staff roles can view or change each page. Administrators always have full access."
      />
      <AccessManager />
    </>
  );
}
