"use client";

import { Bot, RotateCcw, ShieldCheck, Truck } from "lucide-react";

import { CountUp } from "@/components/motion/count-up";
import { Reveal } from "@/components/motion/reveal";
import { Stagger, StaggerItem } from "@/components/motion/stagger";
import { useStorefront } from "@/lib/storefront";

export function WhyVoltHaven() {
  const config = useStorefront().data;
  if (!config) return null;
  const facts = [
    {
      icon: Truck,
      value: config.shipping.express_days,
      suffix: "-day",
      label: "Express delivery",
      detail: `Or standard delivery within ${config.shipping.standard_days} business days.`,
    },
    {
      icon: RotateCcw,
      value: config.returns.window_days,
      suffix: "-day",
      label: "Returns",
      detail: "Changed your mind? Send unused items back for a refund.",
    },
    {
      icon: ShieldCheck,
      value: config.warranty.months,
      suffix: "-month",
      label: "Warranty",
      detail: `On every product, ${config.warranty.extended_months} months with VoltCare+.`,
    },
    {
      icon: Bot,
      value: 24,
      suffix: "/7",
      label: "Support assistant",
      detail: "Report a problem any time; a person reviews every sensitive case.",
    },
  ];
  return (
    <section className="mx-auto max-w-7xl space-y-8 px-4">
      <Reveal className="mx-auto max-w-2xl space-y-2 text-center">
        <h2 className="text-3xl font-semibold tracking-tight">Why shop with VoltHaven</h2>
        <p className="text-muted-foreground">
          Promises we put in writing, in our published policies.
        </p>
      </Reveal>
      <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {facts.map(({ icon: Icon, value, suffix, label, detail }) => (
          <StaggerItem key={label} className="rounded-2xl border bg-card p-6">
            <Icon className="size-6 text-brand" />
            <p className="mt-4 text-4xl font-semibold tracking-tight tabular-nums">
              <CountUp to={value} suffix={suffix} />
            </p>
            <p className="mt-1 font-medium">{label}</p>
            <p className="mt-2 text-sm text-muted-foreground">{detail}</p>
          </StaggerItem>
        ))}
      </Stagger>
    </section>
  );
}
