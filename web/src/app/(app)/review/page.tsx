import { redirect } from "next/navigation";

import { ReviewQueue } from "@/components/complaints/review-queue";
import { PageHeader } from "@/components/page-header";
import { NoAccess } from "@/components/no-access";
import { getCurrentUser } from "@/lib/api/server";
import { can } from "@/lib/access";

export const metadata = { title: "Manual review" };

export default async function ReviewPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "review")) return <NoAccess />;
  return (
    <>
      <PageHeader
        title="Manual review queue"
        description="Complaints where the AI and the Python rules disagree, policy support is missing, the case is sensitive, or a policy changed."
      />
      <ReviewQueue />
    </>
  );
}
