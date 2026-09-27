"use client";

import { MessageCircle, Package, RotateCcw, Search, ShieldCheck, Truck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Reveal } from "@/components/motion/reveal";
import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { FaqAccordion } from "@/components/shop/faq-accordion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { openChat, useStorefront } from "@/lib/storefront";

const TOPICS = [
  {
    href: "/orders",
    icon: Package,
    title: "Track an order",
    text: "See delivery dates and get help.",
  },
  {
    href: "/shipping",
    icon: Truck,
    title: "Shipping",
    text: "Delivery times, late and lost parcels.",
  },
  {
    href: "/returns",
    icon: RotateCcw,
    title: "Returns",
    text: "Send something back, refund timing.",
  },
  {
    href: "/warranty",
    icon: ShieldCheck,
    title: "Warranty",
    text: "Faults, repairs and replacements.",
  },
];

export function HelpContent() {
  const config = useStorefront();
  const [term, setTerm] = useState("");
  const needle = term.trim().toLowerCase();
  const faq = (config.data?.faq ?? []).filter(
    (f) => !needle || `${f.question} ${f.answer}`.toLowerCase().includes(needle),
  );
  return (
    <div className="space-y-16 pb-8">
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,var(--brand-soft),transparent_65%)]" />
        <Reveal className="mx-auto max-w-2xl space-y-6 px-4 py-16 text-center">
          <h1 className="text-5xl font-semibold tracking-tight">How can we help?</h1>
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="Search questions, e.g. refund"
              aria-label="Search help"
              className="h-14 rounded-full bg-background pl-12 text-base shadow-lg shadow-black/5"
            />
          </div>
        </Reveal>
      </section>
      <section className="mx-auto max-w-5xl px-4">
        <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {TOPICS.map(({ href, icon: Icon, title, text }) => (
            <StaggerItem key={href}>
              <Link
                href={href}
                className="block h-full rounded-3xl border bg-card p-5 transition-all hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-lg"
              >
                <Icon className="size-6 text-brand" />
                <p className="mt-3 font-medium">{title}</p>
                <p className="text-sm text-muted-foreground">{text}</p>
              </Link>
            </StaggerItem>
          ))}
        </Stagger>
      </section>
      <section className="mx-auto max-w-3xl space-y-6 px-4">
        <h2 className="text-2xl font-semibold tracking-tight">Frequently asked questions</h2>
        {config.isPending ? (
          <Skeleton className="h-64 rounded-3xl" />
        ) : faq.length ? (
          <FaqAccordion key={needle} items={faq} />
        ) : (
          <p className="rounded-3xl border border-dashed p-8 text-center text-muted-foreground">
            No questions match “{term}”. Try another word, or ask us directly below.
          </p>
        )}
      </section>
      <Reveal className="mx-auto max-w-3xl px-4">
        <div className="flex flex-col items-center gap-4 rounded-[2rem] bg-brand-soft p-10 text-center">
          <h2 className="text-2xl font-semibold tracking-tight">Still need help?</h2>
          <p className="text-muted-foreground">
            Chat with our assistant any time, or send us a message.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Button
              className="rounded-full bg-brand text-brand-foreground"
              onClick={() => openChat()}
            >
              <MessageCircle /> Chat with us
            </Button>
            <Button asChild variant="outline" className="rounded-full bg-background">
              <Link href="/contact">Contact us</Link>
            </Button>
          </div>
        </div>
      </Reveal>
    </div>
  );
}
