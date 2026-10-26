import { redirect } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { ProductsManager } from "@/components/settings/products-manager";
import { NoAccess } from "@/components/no-access";
import { getCurrentUser } from "@/lib/api/server";
import { can } from "@/lib/access";

export const metadata = { title: "Products" };

export default async function ProductsPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok") redirect("/dashboard");
  if (!can(result.user, "products")) return <NoAccess />;
  return (
    <>
      <PageHeader
        title="Products"
        description="The VoltHaven shop catalogue: add and edit products, upload images, hide products from the shop."
      />
      <ProductsManager canEdit={can(result.user, "products", "edit")} />
    </>
  );
}
