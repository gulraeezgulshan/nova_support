import { redirect } from "next/navigation";

import { OrdersManager } from "@/components/fulfilment/orders-manager";
import { PageHeader } from "@/components/page-header";
import { getCurrentUser } from "@/lib/api/server";
import { isStaff } from "@/lib/roles";

export const metadata = { title: "Orders" };

export default async function FulfilmentPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok" || !isStaff(result.user.role)) redirect("/dashboard");
  return (
    <>
      <PageHeader
        title="Orders"
        description="Shop orders and their progress. Moving an order by hand pauses its automatic progress until you resume it."
      />
      <OrdersManager />
    </>
  );
}
