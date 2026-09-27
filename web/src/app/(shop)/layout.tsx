import { ChatLauncher } from "@/components/chat/chat-launcher";
import { SiteFooter } from "@/components/shop/site-footer";
import { SiteHeader } from "@/components/shop/site-header";

export const metadata = {
  title: { absolute: "VoltHaven Electronics", template: "%s · VoltHaven" },
};

export default function ShopLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <SiteHeader />
      <main className="flex-1">{children}</main>
      <SiteFooter />
      <ChatLauncher />
    </div>
  );
}
