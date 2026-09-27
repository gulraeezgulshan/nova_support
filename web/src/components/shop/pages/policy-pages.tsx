"use client";

import Link from "next/link";

import { ArticleLayout, type ArticleSection } from "@/components/shop/article-layout";
import { Button } from "@/components/ui/button";
import type { StorefrontConfig } from "@/lib/api/generated/types.gen";
import { openChat, useStorefront } from "@/lib/storefront";

function HelpAside() {
  return (
    <div className="mt-8 space-y-2 rounded-2xl border bg-muted/30 p-4 text-sm">
      <p className="font-medium">Need a hand?</p>
      <p className="text-muted-foreground">Our assistant can file a problem for you.</p>
      <Button size="sm" className="w-full rounded-full" onClick={() => openChat()}>
        Chat with us
      </Button>
    </div>
  );
}

function days(n: number, unit = "business day") {
  return `${n} ${unit}${n === 1 ? "" : "s"}`;
}

function shippingSections(c: StorefrontConfig): ArticleSection[] {
  const s = c.shipping;
  return [
    {
      id: "options",
      title: "Delivery options",
      body: (
        <>
          <p>
            <strong>Standard delivery</strong> arrives within {days(s.standard_days)} of dispatch.{" "}
            <strong>Express delivery</strong> arrives within {days(s.express_days)} of dispatch.
            Business days don&apos;t include weekends or public holidays.
          </p>
          <p>
            The delivery date shown at checkout is your committed delivery date; it is the date we
            measure any delay against.
          </p>
        </>
      ),
    },
    {
      id: "tracking",
      title: "Tracking your order",
      body: (
        <p>
          Every shipment gets a tracking number by e-mail within {s.tracking_hours} hours of
          dispatch. You can also follow each order in{" "}
          <Link href="/orders" className="text-brand hover:underline">
            My orders
          </Link>
          .
        </p>
      ),
    },
    {
      id: "late",
      title: "If your order is late",
      body: (
        <>
          <p>
            If a standard order arrives more than {days(s.late_threshold_days)} after its committed
            date, you can receive <strong>store credit of {s.late_credit_pct}%</strong> of the order
            value, up to USD {s.late_credit_cap_usd}. If an express order arrives after its
            committed date, we refund the express shipping fee in full.
          </p>
          <p>
            Delays caused by an incorrect address, a missed delivery when nobody was available, or a
            customs inspection aren&apos;t eligible for compensation.
          </p>
        </>
      ),
    },
    {
      id: "lost",
      title: "Lost parcels",
      body: (
        <p>
          A parcel with no tracking movement for {days(s.lost_after_days)} in a row is treated as
          lost. You can then choose a <strong>free replacement</strong> (subject to stock) or a{" "}
          <strong>full refund</strong> of the item and shipping, and we open an investigation with
          the courier.
        </p>
      ),
    },
    {
      id: "damaged",
      title: "Damaged in transit",
      body: (
        <p>
          Please report transit damage within {s.damage_report_hours} hours of delivery, with photos
          of the item and the packaging. Verified damage qualifies for a free replacement or a full
          refund.
        </p>
      ),
    },
  ];
}

function returnsSections(c: StorefrontConfig): ArticleSection[] {
  const r = c.returns;
  return [
    {
      id: "change-of-mind",
      title: "Changed your mind?",
      body: (
        <>
          <p>
            Unused items in their original, undamaged packaging can be returned within{" "}
            <strong>{r.window_days} days of delivery</strong> for a full refund of the item price.
          </p>
          <p>
            Opened software, gift cards, personalised items and hygiene items such as in-ear
            headphones can&apos;t be returned for a change of mind.
          </p>
        </>
      ),
    },
    {
      id: "faulty",
      title: "Faulty or damaged items",
      body: (
        <p>
          Items that are dead on arrival or damaged in transit are refunded in full, including the
          original shipping cost, when reported within {r.defect_report_days} days of delivery.
          We&apos;ll ask for photos or a short video so we can confirm the problem.
        </p>
      ),
    },
    {
      id: "timing",
      title: "When you'll get your money",
      body: (
        <p>
          Approved refunds reach your original payment method within {r.refund_min_days} to{" "}
          {days(r.refund_max_days)} after we receive and inspect the item. Refunds as store credit
          are issued within {days(r.store_credit_days)}. Your bank may take a little longer to show
          the payment.
        </p>
      ),
    },
    {
      id: "partial",
      title: "Partial refunds",
      body: (
        <p>
          Items returned with missing accessories or cosmetic damage after delivery may receive a
          partial refund. We&apos;ll always explain any deduction in writing.
        </p>
      ),
    },
  ];
}

function warrantySections(c: StorefrontConfig): ArticleSection[] {
  const w = c.warranty;
  return [
    {
      id: "coverage",
      title: "What's covered",
      body: (
        <p>
          Every product sold by VoltHaven carries a{" "}
          <strong>{w.months}-month limited warranty</strong> from the delivery date. VoltCare+
          subscribers get an extended warranty of {w.extended_months} months plus accidental-damage
          cover for one claim a year.
        </p>
      ),
    },
    {
      id: "not-covered",
      title: "What isn't covered",
      body: (
        <p>
          Physical or liquid damage (unless you have VoltCare+ accidental-damage cover), normal
          battery wear over time, damage from unauthorised repairs, and cosmetic wear.
        </p>
      ),
    },
    {
      id: "replacement",
      title: "Replacement or repair",
      body: (
        <>
          <p>
            A manufacturing fault reported within {w.replacement_days} days of delivery gets a{" "}
            <strong>new replacement</strong> (or a full refund if it&apos;s out of stock).
          </p>
          <p>
            After that, faulty products are repaired first. Repairs are completed within{" "}
            {days(w.repair_days)} of reaching our service centre, and you&apos;ll get regular status
            updates.
          </p>
        </>
      ),
    },
    {
      id: "claim",
      title: "Making a claim",
      body: (
        <p>
          Start from{" "}
          <Link href="/orders" className="text-brand hover:underline">
            My orders
          </Link>{" "}
          and choose Get help, or{" "}
          <Link href="/contact" className="text-brand hover:underline">
            contact us
          </Link>
          . Have your order, the product&apos;s serial number and a short description of the fault
          ready.
        </p>
      ),
    },
  ];
}

export function ShippingContent() {
  const config = useStorefront().data;
  return (
    <ArticleLayout
      eyebrow="Help · Shipping"
      title="Shipping & delivery"
      lead="How long delivery takes, how to track it, and what happens if something goes wrong."
      sections={config ? shippingSections(config) : null}
      aside={<HelpAside />}
    />
  );
}

export function ReturnsContent() {
  const config = useStorefront().data;
  return (
    <ArticleLayout
      eyebrow="Help · Returns"
      title="Returns & refunds"
      lead="Simple returns, and refunds you can plan around."
      sections={config ? returnsSections(config) : null}
      aside={<HelpAside />}
    />
  );
}

export function WarrantyContent() {
  const config = useStorefront().data;
  return (
    <ArticleLayout
      eyebrow="Help · Warranty"
      title="Warranty"
      lead="What our warranty covers and how to make a claim."
      sections={config ? warrantySections(config) : null}
      aside={<HelpAside />}
    />
  );
}
