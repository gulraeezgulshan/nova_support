import { Show, SignInButton, SignUpButton } from "@clerk/nextjs";
import { BookOpenCheck, PlayCircle, Scale, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { DEMO_VIDEO } from "@/lib/demo-video";

const PILLARS = [
  {
    icon: Sparkles,
    title: "GenAI complaint intelligence",
    text: "Classification, urgency, routing, resolution steps and a professional reply, as structured JSON.",
  },
  {
    icon: Scale,
    title: "Python ground-truth validation",
    text: "Every AI recommendation is checked against the Complaint Resolution Rule Matrix.",
  },
  {
    icon: BookOpenCheck,
    title: "Policy-grounded",
    text: "Only active, versioned company policy is used, and every action cites its source.",
  },
  {
    icon: ShieldCheck,
    title: "Safe by design",
    text: "Complaints are untrusted data: prompt injection cannot approve refunds or skip escalation.",
  },
];

export const metadata = { title: "About SupportNova" };

export default function AboutSupportNovaPage() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col justify-center gap-12 px-6 py-16">
      <div className="space-y-5">
        <p className="text-sm font-medium text-muted-foreground">
          VoltHaven Electronics · Customer Care
        </p>
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">SupportNova</h1>
        <p className="max-w-2xl text-lg text-muted-foreground">
          Complaint resolution intelligence: AI analyses each complaint, Python rules verify it, and
          people stay in control of every decision.
        </p>
        <div className="flex flex-wrap gap-3">
          <Show when="signed-out">
            <SignInButton>
              <Button size="lg">Sign in</Button>
            </SignInButton>
            <SignUpButton>
              <Button size="lg" variant="outline">
                Create customer account
              </Button>
            </SignUpButton>
          </Show>
          <Show when="signed-in">
            <Button size="lg" asChild>
              <Link href="/dashboard">Open dashboard</Link>
            </Button>
          </Show>
          <Button size="lg" variant="ghost" asChild>
            <Link href={DEMO_VIDEO.href}>
              <PlayCircle /> Watch the demo
            </Link>
          </Button>
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {PILLARS.map(({ icon: Icon, title, text }) => (
          <div key={title} className="rounded-xl border p-5">
            <Icon className="mb-3 size-5 text-primary" aria-hidden />
            <h2 className="font-medium">{title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
