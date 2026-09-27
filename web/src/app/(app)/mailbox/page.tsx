import { redirect } from "next/navigation";

import { MailboxConsole } from "@/components/mailbox/mailbox-console";
import { PageHeader } from "@/components/page-header";
import { getCurrentUser } from "@/lib/api/server";

export const metadata = { title: "Mailbox" };

export default async function MailboxPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok" || result.user.role === "customer") redirect("/dashboard");
  return (
    <>
      <PageHeader
        title="Mailbox"
        description="Complaints received by e-mail and the e-mails we sent back."
      />
      <MailboxConsole />
    </>
  );
}
