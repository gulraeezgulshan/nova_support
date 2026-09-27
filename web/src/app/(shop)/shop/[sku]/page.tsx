import { ProductDetail } from "./product-detail";

export default async function ProductPage({ params }: PageProps<"/shop/[sku]">) {
  const { sku } = await params;
  return <ProductDetail sku={sku} />;
}
