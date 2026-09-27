"use client";

import { MessageCircle } from "lucide-react";
import Link from "next/link";

import { Reveal } from "@/components/motion/reveal";
import { NewsletterForm } from "@/components/shop/newsletter-form";
import { Button } from "@/components/ui/button";
import { openChat } from "@/lib/storefront";

export function SupportCallout() {
  return (
    <section className="mx-auto grid max-w-7xl gap-4 px-4 lg:grid-cols-[1.5fr_1fr]">
      <Reveal className="relative overflow-hidden rounded-[2rem] border bg-brand-soft p-8 md:p-12">
        <MessageCircle className="absolute -right-6 -bottom-6 size-48 text-brand/10" />
        <p className="text-sm font-medium tracking-wide text-brand uppercase">
          Support that listens
        </p>
        <h2 className="mt-2 max-w-md text-3xl font-semibold tracking-tight">
          Something wrong with an order? Tell us in your own words.
        </h2>
        <p className="mt-3 max-w-lg text-muted-foreground">
          Our assistant asks a few questions, files it with the right team and replies once a
          specialist-checked answer is ready. Urgent and safety issues go straight to a person.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button
            size="lg"
            className="rounded-full bg-brand text-brand-foreground hover:bg-brand/90"
            onClick={() => openChat()}
          >
            <MessageCircle /> Chat with us
          </Button>
          <Button asChild size="lg" variant="outline" className="rounded-full bg-background">
            <Link href="/help">Visit the help centre</Link>
          </Button>
        </div>
      </Reveal>
      <Reveal
        delay={0.1}
        className="flex flex-col justify-center rounded-[2rem] border bg-card p-8"
      >
        <h2 className="text-2xl font-semibold tracking-tight">Be first to know</h2>
        <p className="mt-2 mb-5 text-sm text-muted-foreground">
          New arrivals and offers, once a month. Unsubscribe any time.
        </p>
        <NewsletterForm source="home" />
      </Reveal>
    </section>
  );
}
