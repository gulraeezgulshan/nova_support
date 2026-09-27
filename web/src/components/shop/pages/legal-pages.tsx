"use client";

import Link from "next/link";

import { ArticleLayout, type ArticleSection } from "@/components/shop/article-layout";
import type { StorefrontConfig } from "@/lib/api/generated/types.gen";
import { useStorefront } from "@/lib/storefront";

const NOTICE = (
  <>
    VoltHaven Electronics is a fictional company created for a student project. This page shows what
    a real shop&apos;s policy would cover; it is not a legal document.
  </>
);

function privacySections(c: StorefrontConfig): ArticleSection[] {
  return [
    {
      id: "what",
      title: "What we collect",
      body: (
        <p>
          Your name and e-mail from your account, your orders, and anything you tell us when you
          contact support. We never ask for your full card number, passwords or one-time codes; if
          you type one into a message, it is automatically hidden before anyone reads it.
        </p>
      ),
    },
    {
      id: "why",
      title: "Why we use it",
      body: (
        <p>
          To deliver your orders, answer your questions and resolve complaints. Support messages are
          analysed by an AI assistant to route them to the right team; decisions that affect you are
          checked against our written policies and, for sensitive cases, by a person.
        </p>
      ),
    },
    {
      id: "rights",
      title: "Your choices",
      body: (
        <p>
          You can ask for a copy of your data or ask us to delete it by{" "}
          <Link href="/contact" className="text-brand hover:underline">
            contacting us
          </Link>
          . We keep records we are required to by law, such as invoices. Newsletter sign-ups are
          stored only so we don&apos;t add you twice; this demo never sends e-mails.
        </p>
      ),
    },
    {
      id: "contact",
      title: "Contact",
      body: (
        <p>
          {c.company.name}, {c.company.address}. E-mail {c.company.support_email}.
        </p>
      ),
    },
  ];
}

function termsSections(c: StorefrontConfig): ArticleSection[] {
  return [
    {
      id: "orders",
      title: "Orders and prices",
      body: (
        <p>
          Prices are shown in US dollars and confirmed when you place your order. This is a demo
          shop: no payment is taken and nothing is shipped.
        </p>
      ),
    },
    {
      id: "delivery",
      title: "Delivery",
      body: (
        <p>
          Standard delivery within {c.shipping.standard_days} business days of dispatch, express
          within {c.shipping.express_days}. See{" "}
          <Link href="/shipping" className="text-brand hover:underline">
            Shipping &amp; delivery
          </Link>{" "}
          for what happens if an order is late or lost.
        </p>
      ),
    },
    {
      id: "returns",
      title: "Returns and warranty",
      body: (
        <p>
          Returns within {c.returns.window_days} days of delivery and a {c.warranty.months}-month
          limited warranty, as described in{" "}
          <Link href="/returns" className="text-brand hover:underline">
            Returns &amp; refunds
          </Link>{" "}
          and{" "}
          <Link href="/warranty" className="text-brand hover:underline">
            Warranty
          </Link>
          . These don&apos;t affect your statutory rights.
        </p>
      ),
    },
    {
      id: "support",
      title: "Complaints",
      body: (
        <p>
          Tell us about any problem through the chat or the{" "}
          <Link href="/contact" className="text-brand hover:underline">
            contact form
          </Link>
          . Every complaint gets a reference number you can follow in your account.
        </p>
      ),
    },
  ];
}

export function PrivacyContent() {
  const config = useStorefront().data;
  return (
    <ArticleLayout
      eyebrow="Legal"
      title="Privacy policy"
      lead={NOTICE}
      sections={config ? privacySections(config) : null}
    />
  );
}

export function TermsContent() {
  const config = useStorefront().data;
  return (
    <ArticleLayout
      eyebrow="Legal"
      title="Terms of sale"
      lead={NOTICE}
      sections={config ? termsSections(config) : null}
    />
  );
}
