import { redirect } from "next/navigation";

import { MailboxConsole } from "@/components/mailbox/mailbox-console";
import { PageHeader } from "@/components/page-header";
import { NoAccess } from "@/components/no-access";
import { getCurrentUser } from "@/lib/api/server";
import { can } from "@/lib/access";

export const metadata = { title: "Mailbox" };

export default async function MailboxPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "mailbox")) return <NoAccess />;
  return (
    <>
      <PageHeader
        title="Mailbox"
        description="Complaints received by e-mail and the e-mails we sent back."
      />
      <MailboxConsole canEdit={can(result.user, "mailbox", "edit")} />
    </>
  );
}
