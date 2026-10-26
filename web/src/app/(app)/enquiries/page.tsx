import { redirect } from "next/navigation";

import { EnquiriesInbox } from "@/components/enquiries/enquiries-inbox";
import { PageHeader } from "@/components/page-header";
import { NoAccess } from "@/components/no-access";
import { getCurrentUser } from "@/lib/api/server";
import { can } from "@/lib/access";

export const metadata = { title: "Enquiries" };

export default async function EnquiriesPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "enquiries")) return <NoAccess />;
  return (
    <>
      <PageHeader
        title="Enquiries"
        description="Contact-form messages that are not complaints: product questions, business enquiries and feedback."
      />
      <EnquiriesInbox canEdit={can(result.user, "enquiries", "edit")} />
    </>
  );
}
