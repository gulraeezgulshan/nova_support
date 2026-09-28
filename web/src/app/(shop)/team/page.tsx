import type { Metadata } from "next";
import Link from "next/link";

import { MemberCard, TechWizBadge } from "@/components/team/team-cards";
import { Button } from "@/components/ui/button";
import { COMPETITION, MENTOR, STUDENTS } from "@/lib/team";

export const metadata: Metadata = {
  title: "Our team",
  description: `The students and mentor who built SupportNova for ${COMPETITION.name}.`,
  openGraph: { images: [COMPETITION.logo] },
};

export default function TeamPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-16 px-4 py-12">
      <section className="grid items-center gap-10 lg:grid-cols-2">
        <div className="space-y-4">
          <p className="text-sm font-medium tracking-wide text-brand uppercase">Our team</p>
          <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
            The people behind SupportNova
          </h1>
          <p className="text-lg text-muted-foreground">
            SupportNova, the complaint intelligence system behind VoltHaven&apos;s customer care,
            was built by five students and their mentor for {COMPETITION.name},{" "}
            {COMPETITION.tagline}.
          </p>
        </div>
        <TechWizBadge />
      </section>

      <section className="space-y-6">
        <h2 className="text-center text-2xl font-semibold tracking-tight">Mentor</h2>
        <div className="mx-auto max-w-sm">
          <MemberCard member={MENTOR} large />
        </div>
      </section>

      <section className="space-y-6">
        <h2 className="text-center text-2xl font-semibold tracking-tight">Students</h2>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
          {STUDENTS.map((s) => (
            <MemberCard key={s.name} member={s} />
          ))}
        </div>
      </section>

      <section className="flex flex-wrap justify-center gap-3 border-t pt-10">
        <Button asChild className="rounded-full bg-brand text-brand-foreground">
          <Link href="/blog/letting-the-model-talk">Read how we built it</Link>
        </Button>
        <Button asChild variant="outline" className="rounded-full">
          <Link href="/about-supportnova">How our support works</Link>
        </Button>
      </section>
    </div>
  );
}
