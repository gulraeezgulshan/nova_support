"use client";

import { Clock, Mail, MapPin, MessageCircle, Phone } from "lucide-react";

import { Reveal } from "@/components/motion/reveal";
import { ContactForm } from "@/components/shop/contact-form";
import { Button } from "@/components/ui/button";
import { openChat, useStorefront } from "@/lib/storefront";

export function ContactContent() {
  const company = useStorefront().data?.company;
  const details = company
    ? [
        { icon: Phone, label: "Phone", value: company.phone },
        { icon: Mail, label: "E-mail", value: company.support_email },
        { icon: Clock, label: "Hours", value: company.hours },
        { icon: MapPin, label: "Address", value: company.address },
      ]
    : [];
  return (
    <div className="mx-auto max-w-7xl px-4 py-12">
      <Reveal className="max-w-2xl space-y-3">
        <p className="text-sm font-medium tracking-wide text-brand uppercase">Contact us</p>
        <h1 className="text-5xl font-semibold tracking-tight">We&apos;re here to help</h1>
        <p className="text-lg text-muted-foreground">
          Send us a message and the right team will pick it up. Problems with an order are filed as
          complaints straight away.
        </p>
      </Reveal>
      <div className="mt-12 grid gap-10 lg:grid-cols-[1.6fr_1fr]">
        <Reveal delay={0.05} className="rounded-3xl border p-6 sm:p-8">
          <ContactForm />
        </Reveal>
        <Reveal delay={0.1} className="space-y-4">
          <div className="rounded-3xl bg-zinc-950 p-6 text-white">
            <MessageCircle className="size-6 text-brand" />
            <p className="mt-3 text-lg font-semibold">Fastest: chat with us</p>
            <p className="mt-1 text-sm text-zinc-300">
              Our assistant asks a few questions and files it for you, any time of day.
            </p>
            <Button
              className="mt-4 rounded-full bg-white text-zinc-950 hover:bg-white/90"
              onClick={() => openChat()}
            >
              Start a chat
            </Button>
          </div>
          <ul className="divide-y rounded-3xl border">
            {details.map(({ icon: Icon, label, value }) => (
              <li key={label} className="flex gap-4 p-5">
                <Icon className="mt-0.5 size-5 shrink-0 text-brand" />
                <div>
                  <p className="text-sm font-medium">{label}</p>
                  <p className="text-sm text-muted-foreground">{value}</p>
                </div>
              </li>
            ))}
          </ul>
        </Reveal>
      </div>
    </div>
  );
}
