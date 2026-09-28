import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { StackDiagram } from "@/components/stack/stack-diagram";
import { StackGrid } from "@/components/stack/stack-grid";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TOUR } from "@/lib/tour";

export const metadata: Metadata = {
  title: "How it works",
  description:
    "A tour of SupportNova: the technology behind it and every part of the app, with screenshots.",
  openGraph: { images: ["/tour/diagram.png"] },
};

export default function HowItWorksPage() {
  return (
    <div className="mx-auto max-w-7xl space-y-20 px-4 py-12">
      <header className="max-w-3xl space-y-4">
        <p className="text-sm font-medium tracking-wide text-brand uppercase">How it works</p>
        <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          Inside SupportNova
        </h1>
        <p className="text-lg text-muted-foreground">
          The technology behind VoltHaven&apos;s complaint handling, and a tour of every part of the
          app: what customers see, and what support staff work with.
        </p>
        <nav aria-label="On this page" className="flex flex-wrap gap-2 pt-2">
          <a href="#stack" className="text-sm font-medium text-brand hover:underline">
            The stack
          </a>
          <span className="text-muted-foreground">·</span>
          <a href="#tech" className="text-sm font-medium text-brand hover:underline">
            Tech we used
          </a>
          <span className="text-muted-foreground">·</span>
          <a href="#tour" className="text-sm font-medium text-brand hover:underline">
            Tour of the app
          </a>
        </nav>
      </header>

      <section id="stack" className="scroll-mt-24 space-y-6">
        <h2 className="text-3xl font-semibold tracking-tight">The stack at a glance</h2>
        <StackDiagram />
      </section>

      <section id="tech" className="scroll-mt-24 space-y-6">
        <h2 className="text-3xl font-semibold tracking-tight">Tech we used</h2>
        <StackGrid />
      </section>

      {TOUR.length > 0 && (
        <section id="tour" className="scroll-mt-24 space-y-12">
          <div className="max-w-3xl space-y-3">
            <h2 className="text-3xl font-semibold tracking-tight">Tour of the app</h2>
            <p className="text-muted-foreground">
              Screenshots from the live application. Staff screens need a sign-in; these show what
              an administrator sees, with customers&apos; e-mail addresses masked.
            </p>
          </div>
          <ol className="space-y-20">
            {TOUR.map((stop, i) => (
              <li
                key={stop.image}
                id={stop.id}
                className="grid scroll-mt-24 items-center gap-8 lg:grid-cols-5"
              >
                <a
                  href={stop.image}
                  target="_blank"
                  rel="noreferrer"
                  title="Open full size"
                  className={`lg:col-span-3 ${i % 2 ? "lg:order-last" : ""}`}
                >
                  <Image
                    src={stop.image}
                    alt={`Screenshot: ${stop.title}`}
                    width={1440}
                    height={900}
                    sizes="(min-width: 1024px) 60vw, 100vw"
                    className="rounded-2xl border shadow-sm"
                  />
                </a>
                <div className="space-y-3 lg:col-span-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-muted-foreground tabular-nums">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <Badge variant="secondary">{stop.area}</Badge>
                  </div>
                  <h3 className="text-2xl font-semibold tracking-tight">{stop.title}</h3>
                  {stop.text.map((p) => (
                    <p key={p} className="text-muted-foreground">
                      {p}
                    </p>
                  ))}
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="flex flex-wrap justify-center gap-3 border-t pt-10">
        <Button asChild className="rounded-full bg-brand text-brand-foreground">
          <Link href="/blog/letting-the-model-talk">Read the engineering blog</Link>
        </Button>
        <Button asChild variant="outline" className="rounded-full">
          <Link href="/team">Meet the team</Link>
        </Button>
      </section>
    </div>
  );
}
