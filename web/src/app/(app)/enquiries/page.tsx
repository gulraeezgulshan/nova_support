import { redirect } from "next/navigation";

import { EnquiriesInbox } from "@/components/enquiries/enquiries-inbox";
import { PageHeader } from "@/components/page-header";
import { getCurrentUser } from "@/lib/api/server";

export const metadata = { title: "Enquiries" };

export default async function EnquiriesPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok" || result.user.role === "customer") redirect("/dashboard");
  return (
    <>
      <PageHeader
        title="Enquiries"
        description="Contact-form messages that are not complaints: product questions, business enquiries and feedback."
      />
      <EnquiriesInbox />
    </>
  );
}
