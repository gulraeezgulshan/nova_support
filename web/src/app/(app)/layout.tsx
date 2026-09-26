import { UserButton } from "@clerk/nextjs";
import { AlertTriangle } from "lucide-react";
import { redirect } from "next/navigation";

import { AppSidebar } from "@/components/app-sidebar";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { getCurrentUser } from "@/lib/api/server";

export default async function AppLayout({ children }: LayoutProps<"/">) {
  const result = await getCurrentUser();
  if (result.status === "signed-out") redirect("/sign-in");
  if (result.status === "unavailable") {
    return (
      <main className="mx-auto max-w-xl p-10">
        <Alert variant="destructive">
          <AlertTriangle />
          <AlertTitle>SupportNova API is unavailable</AlertTitle>
          <AlertDescription>{result.message}</AlertDescription>
        </Alert>
      </main>
    );
  }

  return (
    <SidebarProvider>
      <AppSidebar user={result.user} />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
          <span className="text-sm text-muted-foreground">VoltHaven Electronics</span>
          <div className="ml-auto">
            <UserButton />
          </div>
        </header>
        <div className="flex-1 p-4 md:p-6">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  );
}
