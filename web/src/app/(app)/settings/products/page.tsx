import { redirect } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { ProductsManager } from "@/components/settings/products-manager";
import { getCurrentUser } from "@/lib/api/server";

export const metadata = { title: "Products" };

export default async function ProductsPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok" || result.user.role !== "admin") redirect("/dashboard");
  return (
    <>
      <PageHeader
        title="Products"
        description="The VoltHaven shop catalogue: add and edit products, upload images, hide products from the shop."
      />
      <ProductsManager />
    </>
  );
}
