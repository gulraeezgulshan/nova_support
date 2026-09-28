import { redirect } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { SettingsManager } from "@/components/settings/settings-manager";
import { getCurrentUser } from "@/lib/api/server";

export const metadata = { title: "Settings" };

export default async function SettingsPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok" || result.user.role !== "admin") redirect("/dashboard");
  return (
    <>
      <PageHeader
        title="Settings"
        description="E-mail timing, AI behaviour, review thresholds and branding. Changes apply within about 15 seconds, with no redeploy. Keys and passwords stay on the server."
      />
      <SettingsManager />
    </>
  );
}
