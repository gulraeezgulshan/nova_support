"use client";

import Link from "next/link";

import { PRODUCT_LINES } from "@/components/shop/lines";
import { NewsletterForm } from "@/components/shop/newsletter-form";
import { Logo } from "@/components/shop/site-header";
import { ThemeToggle } from "@/components/shop/theme-toggle";
import { useStorefront } from "@/lib/storefront";

const COLUMNS: { title: string; links: { href: string; label: string }[] }[] = [
  {
    title: "Shop",
    links: [
      { href: "/shop", label: "All products" },
      ...PRODUCT_LINES.slice(0, 5).map((l) => ({ href: `/shop?line=${l.code}`, label: l.label })),
    ],
  },
  {
    title: "Support",
    links: [
      { href: "/help", label: "Help centre" },
      { href: "/orders", label: "Track an order" },
      { href: "/contact", label: "Contact us" },
      { href: "/shipping", label: "Shipping & delivery" },
      { href: "/returns", label: "Returns & refunds" },
      { href: "/warranty", label: "Warranty" },
    ],
  },
  {
    title: "Company",
    links: [
      { href: "/about", label: "About VoltHaven" },
      { href: "/about-supportnova", label: "How our support works" },
      { href: "/blog", label: "Blog" },
      { href: "/contact", label: "Business enquiries" },
    ],
  },
  {
    title: "Legal",
    links: [
      { href: "/privacy", label: "Privacy policy" },
      { href: "/terms", label: "Terms of sale" },
    ],
  },
];

export function SiteFooter() {
  const config = useStorefront();
  const company = config.data?.company;
  return (
    <footer className="mt-24 border-t bg-muted/30">
      <div className="mx-auto max-w-7xl px-4 py-14">
        <div className="grid gap-10 lg:grid-cols-[1.4fr_2fr]">
          <div className="space-y-4">
            <Logo />
            <p className="max-w-sm text-sm text-muted-foreground">
              {company?.tagline ?? "Electronics that just work, and support that listens."}
            </p>
            <div className="max-w-sm space-y-2">
              <p className="text-sm font-medium">Get launch news and offers</p>
              <NewsletterForm source="footer" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
            {COLUMNS.map((column) => (
              <div key={column.title} className="space-y-3">
                <p className="text-sm font-semibold">{column.title}</p>
                <ul className="space-y-2">
                  {column.links.map((link) => (
                    <li key={`${column.title}-${link.label}`}>
                      <Link
                        href={link.href}
                        className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-12 flex flex-col gap-4 border-t pt-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1 text-xs text-muted-foreground">
            <p>
              © {new Date().getFullYear()} {company?.name ?? "VoltHaven Electronics"}.{" "}
              {company ? `${company.phone} · ${company.support_email}` : null}
            </p>
            <p>
              VoltHaven Electronics is a fictional company created for a student project. No real
              orders, payments or deliveries take place.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {company?.socials.map((s) => (
              <a
                key={s.name}
                href={s.url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                {s.name}
              </a>
            ))}
            <ThemeToggle />
          </div>
        </div>
      </div>
    </footer>
  );
}
