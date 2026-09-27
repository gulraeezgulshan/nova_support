import { CategoryRow } from "@/components/shop/home/category-row";
import { FeatureSpotlight } from "@/components/shop/home/feature-spotlight";
import { Hero } from "@/components/shop/home/hero";
import { SupportCallout } from "@/components/shop/home/support-callout";
import { WhyVoltHaven } from "@/components/shop/home/why-volthaven";
import { ProductCarousel } from "@/components/shop/product-carousel";

export default function HomePage() {
  return (
    <div className="space-y-24 pb-8">
      <Hero />
      <CategoryRow />
      <ProductCarousel
        title="New arrivals"
        subtitle="The latest additions to the range."
        sort="newest"
        href="/shop?sort=newest"
      />
      <FeatureSpotlight sku="VH-LAP-AB14" />
      <ProductCarousel
        title="Best sellers"
        subtitle="What customers bought most in the last 90 days."
        sort="best_selling"
        href="/shop?sort=best_selling"
      />
      <WhyVoltHaven />
      <SupportCallout />
    </div>
  );
}
