import { redirect } from "next/navigation";

import { OrdersManager } from "@/components/fulfilment/orders-manager";
import { PageHeader } from "@/components/page-header";
import { NoAccess } from "@/components/no-access";
import { getCurrentUser } from "@/lib/api/server";
import { can } from "@/lib/access";

export const metadata = { title: "Orders" };

export default async function FulfilmentPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "orders")) return <NoAccess />;
  return (
    <>
      <PageHeader
        title="Orders"
        description="Shop orders and their progress. Moving an order by hand pauses its automatic progress until you resume it."
      />
      <OrdersManager canEdit={can(result.user, "orders", "edit")} />
    </>
  );
}
