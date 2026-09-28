"use client";

import { HeartHandshake, Leaf, Sparkles, Wrench } from "lucide-react";
import Link from "next/link";

import { CountUp } from "@/components/motion/count-up";
import { Reveal } from "@/components/motion/reveal";
import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { PRODUCT_LINES } from "@/components/shop/lines";
import { useCategories } from "@/components/shop/use-categories";
import { Button } from "@/components/ui/button";
import { useStorefront } from "@/lib/storefront";

const VALUES = [
  {
    icon: Sparkles,
    title: "Fewer, better products",
    text: "We test every product line ourselves and only sell what we would recommend to friends.",
  },
  {
    icon: HeartHandshake,
    title: "Support that listens",
    text: "Tell us what happened in your own words. The right team picks it up, with a reference you can follow.",
  },
  {
    icon: Wrench,
    title: "Built to be repaired",
    text: "Warranty repairs come first, so good devices stay in use for longer.",
  },
  {
    icon: Leaf,
    title: "Honest promises",
    text: "Our delivery, returns and warranty terms are published in full, and our support follows them.",
  },
];

export function AboutContent() {
  const config = useStorefront().data;
  const total = useCategories().reduce((n, c) => n + c.count, 0);
  const stats = config
    ? [
        { value: PRODUCT_LINES.length, suffix: "", label: "product categories" },
        { value: total, suffix: "", label: "carefully chosen products" },
        { value: config.warranty.months, suffix: "-month", label: "warranty on everything" },
        { value: 24, suffix: "/7", label: "support assistant" },
      ]
    : [];
  return (
    <div className="space-y-24 pb-8">
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,var(--brand-soft),transparent_60%)]" />
        <Reveal className="mx-auto max-w-3xl space-y-6 px-4 py-20 text-center">
          <p className="text-sm font-medium tracking-wide text-brand uppercase">About us</p>
          <h1 className="text-5xl font-semibold tracking-tight text-balance sm:text-6xl">
            Technology should make life easier, not harder.
          </h1>
          <p className="text-lg text-muted-foreground">
            VoltHaven started with a simple idea: sell electronics people actually love, and look
            after them properly when something goes wrong. Everything we do, from choosing products
            to answering complaints, follows from that.
          </p>
        </Reveal>
      </section>
      <section className="mx-auto max-w-7xl px-4">
        <Stagger className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {stats.map((s) => (
            <StaggerItem key={s.label} className="rounded-3xl border bg-card p-6 text-center">
              <p className="text-4xl font-semibold tracking-tight tabular-nums">
                <CountUp to={s.value} suffix={s.suffix} />
              </p>
              <p className="mt-1 text-sm text-muted-foreground">{s.label}</p>
            </StaggerItem>
          ))}
        </Stagger>
      </section>
      <section className="mx-auto grid max-w-7xl items-center gap-12 px-4 lg:grid-cols-2">
        <Reveal className="space-y-4">
          <h2 className="text-3xl font-semibold tracking-tight">Our story</h2>
          <p className="text-muted-foreground">
            We began as a small repair counter, fixing phones and laptops that other shops had given
            up on. Customers kept asking us what to buy next, so we started stocking the products we
            trusted.
          </p>
          <p className="text-muted-foreground">
            Today we sell across {PRODUCT_LINES.length} categories, from phones and laptops to smart
            home, but the repair-counter attitude hasn&apos;t changed: if something goes wrong, we
            want to hear about it and put it right.
          </p>
        </Reveal>
        <Reveal delay={0.1} className="rounded-[2rem] bg-zinc-950 p-10 text-white">
          <p className="text-2xl leading-snug font-medium">
            &ldquo;Every complaint is a chance to show what kind of shop we are.&rdquo;
          </p>
          <p className="mt-6 text-sm text-zinc-400">— The VoltHaven customer care team</p>
        </Reveal>
      </section>
      <section className="mx-auto max-w-7xl space-y-8 px-4">
        <Reveal>
          <h2 className="text-3xl font-semibold tracking-tight">What we care about</h2>
        </Reveal>
        <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {VALUES.map(({ icon: Icon, title, text }) => (
            <StaggerItem key={title} className="rounded-3xl border bg-card p-6">
              <Icon className="size-6 text-brand" />
              <h3 className="mt-4 font-semibold">{title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{text}</p>
            </StaggerItem>
          ))}
        </Stagger>
      </section>
      <Reveal className="mx-auto max-w-3xl space-y-4 px-4 text-center">
        <h2 className="text-3xl font-semibold tracking-tight">Curious how our support works?</h2>
        <p className="text-muted-foreground">
          Complaints are analysed by AI and checked against our written rules before anyone replies.
          VoltHaven is a fictional shop built to demonstrate that system.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Button asChild className="rounded-full bg-brand text-brand-foreground">
            <Link href="/about-supportnova">How our support works</Link>
          </Button>
          <Button asChild variant="outline" className="rounded-full">
            <Link href="/blog/letting-the-model-talk">Read the engineering blog</Link>
          </Button>
          <Button asChild variant="outline" className="rounded-full">
            <Link href="/team">Meet the team</Link>
          </Button>
          <Button asChild variant="outline" className="rounded-full">
            <Link href="/contact">Contact us</Link>
          </Button>
        </div>
      </Reveal>
    </div>
  );
}
