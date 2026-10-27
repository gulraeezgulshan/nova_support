import { redirect } from "next/navigation";

import { NoAccess } from "@/components/no-access";
import { PageHeader } from "@/components/page-header";
import { TextsManager } from "@/components/settings/texts-manager";
import { can } from "@/lib/access";
import { getCurrentUser } from "@/lib/api/server";

export const metadata = { title: "Customer texts" };

export default async function CustomerTextsPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "settings")) return <NoAccess />;
  return (
    <>
      <PageHeader
        title="Customer texts"
        description="E-mails and chat messages customers receive. Placeholders in braces are filled in when a message is sent; the preview uses sample values."
      />
      <TextsManager />
    </>
  );
}
