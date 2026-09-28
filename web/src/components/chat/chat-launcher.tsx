"use client";

import { X } from "lucide-react";
import { useEffect, useState } from "react";

import { ChatPanel } from "@/components/chat/chat-panel";
import { NovaAvatar } from "@/components/chat/nova-avatar";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

const GREETED = "nova-greeted"; // the greeting bubble shows once per browser session
const GREETING_DELAY_MS = 4000;

function greetedAlready(): boolean {
  try {
    return window.sessionStorage.getItem(GREETED) === "1";
  } catch {
    return false;
  }
}

function rememberGreeted() {
  try {
    window.sessionStorage.setItem(GREETED, "1");
  } catch {
    // storage unavailable (private mode): the bubble may show again, which is harmless
  }
}

export function ChatLauncher() {
  const [open, setOpen] = useState(false);
  const [orderRef, setOrderRef] = useState<string | undefined>();
  const [session, setSession] = useState(0); // new panel instance per opening context
  const [greeting, setGreeting] = useState(false);

  useEffect(() => {
    const handler = (event: Event) => {
      setOrderRef((event as CustomEvent<{ orderRef?: string }>).detail?.orderRef);
      setSession((s) => s + 1);
      setOpen(true);
    };
    window.addEventListener("volthaven:open-chat", handler);
    return () => window.removeEventListener("volthaven:open-chat", handler);
  }, []);

  useEffect(() => {
    if (greetedAlready()) return;
    const timer = window.setTimeout(() => setGreeting(true), GREETING_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, []);

  function dismissGreeting() {
    setGreeting(false);
    rememberGreeted();
  }

  function openChat() {
    dismissGreeting();
    setOrderRef(undefined);
    setSession((s) => s + 1);
    setOpen(true);
  }

  return (
    <>
      <div className="fixed right-4 bottom-4 z-40 flex flex-col items-end gap-2">
        {greeting && !open ? (
          <div className="relative max-w-60 animate-in rounded-2xl border bg-card px-4 py-3 pr-8 text-sm shadow-lg fade-in slide-in-from-bottom-2">
            <button
              type="button"
              onClick={openChat}
              className="text-left"
              aria-label="Open the support chat"
            >
              <span className="font-semibold">Hi, I&apos;m Nova!</span> Need help with an order or a
              product? Ask me here.
            </button>
            <button
              type="button"
              onClick={dismissGreeting}
              className="absolute top-2 right-2 rounded-full p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label="Dismiss"
            >
              <X className="size-3.5" />
            </button>
          </div>
        ) : null}
        <button
          type="button"
          onClick={openChat}
          className="group grid size-16 place-items-center rounded-full border bg-card shadow-lg ring-brand/30 transition-transform hover:scale-105 focus-visible:ring-4 focus-visible:outline-none"
          aria-label="Chat with Nova, the VoltHaven support assistant"
          title="Chat with Nova"
        >
          <NovaAvatar className="size-12 transition-transform group-hover:-rotate-6" />
        </button>
      </div>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className="flex w-full flex-col gap-0 p-0 sm:max-w-md">
          <SheetHeader className="border-b">
            <div className="flex items-center gap-3">
              <NovaAvatar className="size-10" />
              <div>
                <SheetTitle>Nova</SheetTitle>
                <SheetDescription>VoltHaven support assistant</SheetDescription>
              </div>
            </div>
          </SheetHeader>
          {open ? <ChatPanel key={session} orderRef={orderRef} /> : null}
        </SheetContent>
      </Sheet>
    </>
  );
}
