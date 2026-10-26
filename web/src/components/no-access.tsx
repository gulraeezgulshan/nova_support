import { ShieldOff } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

/** Shown instead of a staff page the user's role may not open. */
export function NoAccess({ backToDashboard = true }: { backToDashboard?: boolean }) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 text-center">
      <ShieldOff className="size-10 text-muted-foreground" aria-hidden />
      <h1 className="text-xl font-semibold">You don&apos;t have access to this page</h1>
      <p className="text-muted-foreground">Ask an administrator.</p>
      {backToDashboard ? (
        <Button asChild variant="outline">
          <Link href="/dashboard">Back to dashboard</Link>
        </Button>
      ) : null}
    </div>
  );
}
