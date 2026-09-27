"use client";

import { MessageCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { ChatPanel } from "@/components/chat/chat-panel";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";

export function ChatLauncher() {
  const [open, setOpen] = useState(false);
  const [orderRef, setOrderRef] = useState<string | undefined>();
  const [session, setSession] = useState(0); // new panel instance per opening context

  useEffect(() => {
    const handler = (event: Event) => {
      setOrderRef((event as CustomEvent<{ orderRef?: string }>).detail?.orderRef);
      setSession((s) => s + 1);
      setOpen(true);
    };
    window.addEventListener("volthaven:open-chat", handler);
    return () => window.removeEventListener("volthaven:open-chat", handler);
  }, []);

  return (
    <>
      <Button
        size="lg"
        className="fixed right-4 bottom-4 z-40 rounded-full shadow-lg"
        onClick={() => {
          setOrderRef(undefined);
          setSession((s) => s + 1);
          setOpen(true);
        }}
      >
        <MessageCircle /> Help
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className="flex w-full flex-col gap-0 p-0 sm:max-w-md">
          <SheetHeader className="border-b">
            <SheetTitle>VoltHaven support</SheetTitle>
          </SheetHeader>
          {open ? <ChatPanel key={session} orderRef={orderRef} /> : null}
        </SheetContent>
      </Sheet>
    </>
  );
}
