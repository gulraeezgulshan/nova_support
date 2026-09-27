import { NotFoundContent } from "@/components/shop/not-found-content";
import { SiteFooter } from "@/components/shop/site-footer";
import { SiteHeader } from "@/components/shop/site-header";

export const metadata = { title: "Page not found" };

/** Unmatched URLs: the shop's 404 with its header and footer. */
export default function NotFound() {
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <SiteHeader />
      <main className="flex-1">
        <NotFoundContent />
      </main>
      <SiteFooter />
    </div>
  );
}
