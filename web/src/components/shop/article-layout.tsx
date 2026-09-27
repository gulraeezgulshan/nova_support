"use client";

import { useEffect, useState } from "react";

import { Reveal } from "@/components/motion/reveal";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export type ArticleSection = { id: string; title: string; body: React.ReactNode };

/** Long-form page: header, sticky table of contents that follows your reading position. */
export function ArticleLayout({
  eyebrow,
  title,
  lead,
  updated,
  sections,
  aside,
}: {
  eyebrow: string;
  title: string;
  lead: React.ReactNode;
  updated?: string;
  sections: ArticleSection[] | null;
  aside?: React.ReactNode;
}) {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    if (!sections) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length) setActive(visible[0].target.id);
      },
      { rootMargin: "-20% 0px -70% 0px" },
    );
    for (const s of sections) {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [sections]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-12">
      <Reveal className="max-w-3xl space-y-4 border-b pb-10">
        <p className="text-sm font-medium tracking-wide text-brand uppercase">{eyebrow}</p>
        <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">{title}</h1>
        <div className="text-lg text-muted-foreground">{lead}</div>
        {updated ? <p className="text-xs text-muted-foreground">{updated}</p> : null}
      </Reveal>
      <div className="mt-10 grid gap-12 lg:grid-cols-[14rem_1fr]">
        <nav aria-label="On this page" className="hidden lg:block">
          <div className="sticky top-24 space-y-3">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              On this page
            </p>
            <ul className="space-y-1 border-l">
              {(sections ?? []).map((s) => (
                <li key={s.id}>
                  <a
                    href={`#${s.id}`}
                    className={cn(
                      "-ml-px block border-l-2 border-transparent py-1 pl-4 text-sm text-muted-foreground transition-colors hover:text-foreground",
                      active === s.id && "border-brand font-medium text-foreground",
                    )}
                  >
                    {s.title}
                  </a>
                </li>
              ))}
            </ul>
            {aside}
          </div>
        </nav>
        <article className="max-w-3xl space-y-12">
          {sections ? (
            sections.map((s) => (
              <section key={s.id} id={s.id} className="scroll-mt-24 space-y-3">
                <h2 className="text-2xl font-semibold tracking-tight">{s.title}</h2>
                <div className="space-y-3 leading-relaxed text-muted-foreground [&_strong]:text-foreground">
                  {s.body}
                </div>
              </section>
            ))
          ) : (
            <div className="space-y-4">
              <Skeleton className="h-8 w-1/2" />
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
            </div>
          )}
        </article>
      </div>
    </div>
  );
}
