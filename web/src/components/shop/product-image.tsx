import { ProductArt } from "@/components/shop/product-art";
import { API_URL } from "@/lib/api/runtime-config";
import { cn } from "@/lib/utils";

/** A product photo when one has been uploaded, otherwise the product-line illustration. */
export function ProductImage({
  url,
  line,
  alt,
  className,
}: {
  url?: string | null;
  line: string;
  alt: string;
  className?: string;
}) {
  if (!url) return <ProductArt line={line} className={className} />;
  return (
    // Plain <img>: images come from the API host and are already sized by the admin.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`${API_URL}${url}`}
      alt={alt}
      loading="lazy"
      className={cn("aspect-square rounded-xl bg-white object-contain", className)}
    />
  );
}
