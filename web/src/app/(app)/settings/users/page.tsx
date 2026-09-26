import { redirect } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { UsersTable } from "@/components/settings/users-table";
import { getCurrentUser } from "@/lib/api/server";

export const metadata = { title: "Users & roles" };

export default async function UsersPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok" || !["admin", "manager"].includes(result.user.role)) {
    redirect("/dashboard");
  }

  return (
    <>
      <PageHeader
        title="Users & roles"
        description="People sign in with Clerk; their SupportNova role and department are managed here."
      />
      <UsersTable canManage={result.user.role === "admin"} currentUserId={result.user.id} />
    </>
  );
}
