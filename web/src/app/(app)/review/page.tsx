import { redirect } from "next/navigation";

import { ReviewQueue } from "@/components/complaints/review-queue";
import { PageHeader } from "@/components/page-header";
import { getCurrentUser } from "@/lib/api/server";

export const metadata = { title: "Manual review" };

export default async function ReviewPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok" || !["reviewer", "manager", "admin"].includes(result.user.role)) {
    redirect("/dashboard");
  }
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
