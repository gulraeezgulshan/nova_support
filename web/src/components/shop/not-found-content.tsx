import Link from "next/link";

import { Button } from "@/components/ui/button";

/** Friendly 404 body, used inside the shop layout and by the root not-found page. */
export function NotFoundContent() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center gap-6 px-4 py-28 text-center">
      <p className="bg-gradient-to-b from-brand to-brand/30 bg-clip-text text-8xl font-semibold tracking-tighter text-transparent">
        404
      </p>
      <h1 className="text-3xl font-semibold tracking-tight">This page has gone off-grid</h1>
      <p className="text-muted-foreground">
        The page you&apos;re looking for doesn&apos;t exist or has moved. Try the shop, or visit our
        help centre.
      </p>
      <div className="flex flex-wrap justify-center gap-3">
        <Button asChild className="rounded-full bg-brand text-brand-foreground">
          <Link href="/shop">Go to the shop</Link>
        </Button>
        <Button asChild variant="outline" className="rounded-full">
          <Link href="/help">Help centre</Link>
        </Button>
      </div>
    </div>
  );
}
