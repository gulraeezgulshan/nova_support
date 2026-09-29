import type { Metadata } from "next";

import { ChatLauncher } from "@/components/chat/chat-launcher";
import { CurrencyProvider } from "@/lib/currency";
import { SiteFooter } from "@/components/shop/site-footer";
import { SiteHeader } from "@/components/shop/site-header";

const SERVER_API_URL =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function generateMetadata(): Promise<Metadata> {
  try {
    const res = await fetch(`${SERVER_API_URL}/api/v1/branding`, { next: { revalidate: 60 } });
    const b = (await res.json()) as { shop_name: string; shop_logo_url: string | null };
    return {
      title: { absolute: b.shop_name, template: `%s · ${b.shop_name.split(" ")[0]}` },
      icons: b.shop_logo_url ? { icon: `${SERVER_API_URL}${b.shop_logo_url}` } : undefined,
    };
  } catch {
    return { title: { absolute: "VoltHaven Electronics", template: "%s · VoltHaven" } };
  }
}

export default function ShopLayout({ children }: LayoutProps<"/">) {
  return (
    <CurrencyProvider>
      <div className="flex min-h-dvh flex-col bg-background">
        <SiteHeader />
        <main className="flex-1">{children}</main>
        <SiteFooter />
        <ChatLauncher />
      </div>
    </CurrencyProvider>
  );
}
