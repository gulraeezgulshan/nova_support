import { redirect } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { UsersTable } from "@/components/settings/users-table";
import { NoAccess } from "@/components/no-access";
import { getCurrentUser } from "@/lib/api/server";
import { can } from "@/lib/access";

export const metadata = { title: "Users & roles" };

export default async function UsersPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "users")) return <NoAccess />;

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
