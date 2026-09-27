"use client";

import { MessageCircle } from "lucide-react";

import { Reveal } from "@/components/motion/reveal";
import { OrderList } from "@/components/shop/order-list";
import { Button } from "@/components/ui/button";
import { openChat } from "@/lib/storefront";

export default function OrdersPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-10">
      <Reveal className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-4xl font-semibold tracking-tight">My orders</h1>
          <p className="text-muted-foreground">
            Problem with an order? Use Get help and our assistant will take it from there.
          </p>
        </div>
        <Button variant="outline" className="rounded-full" onClick={() => openChat()}>
          <MessageCircle /> Chat with us
        </Button>
      </Reveal>
      <OrderList onHelp={openChat} />
    </div>
  );
}
