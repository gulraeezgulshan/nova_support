"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";

import { CountUp } from "@/components/motion/count-up";
import { EASE_OUT, Reveal } from "@/components/motion/reveal";
import { ProductImage } from "@/components/shop/product-image";
import { Button } from "@/components/ui/button";
import { getProductOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import { Price } from "@/lib/currency";

const NUMBER = /^(\d+(?:[.,]\d+)?)(.*)$/;

/** "16 GB RAM" → a count-up 16 with " GB RAM"; specs without a leading number stay text. */
function Spec({ text }: { text: string }) {
  const match = NUMBER.exec(text);
  if (!match) return <span className="text-2xl font-semibold tracking-tight">{text}</span>;
  const [, number, rest] = match;
  const value = Number(number.replace(",", ""));
  const decimals = number.includes(".") ? number.split(".")[1].length : 0;
  return (
    <span className="text-2xl font-semibold tracking-tight">
      {number.includes(",") ? number : <CountUp to={value} decimals={decimals} />}
      <span className="text-base font-normal text-muted-foreground">{rest}</span>
    </span>
  );
}

export function FeatureSpotlight({ sku }: { sku: string }) {
  const product = useQuery(getProductOptions({ path: { sku } }));
  if (!product.data) return null;
  const p = product.data;
  return (
    <section className="mx-auto max-w-7xl px-4">
      <div className="relative overflow-hidden rounded-[2rem] bg-zinc-950 text-white">
        <div className="pointer-events-none absolute -top-40 -right-40 size-[32rem] rounded-full bg-brand/40 blur-3xl" />
        <div className="relative grid items-center gap-10 p-8 md:p-14 lg:grid-cols-2">
          <div className="space-y-6">
            <Reveal>
              <p className="text-sm font-medium tracking-wide text-brand uppercase">Spotlight</p>
              <h2 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">{p.name}</h2>
              <p className="mt-3 max-w-md text-zinc-300">{p.description}</p>
            </Reveal>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-5">
              {p.specs.slice(0, 4).map((spec, i) => (
                <Reveal key={spec} delay={0.1 * i} className="border-l border-white/15 pl-4">
                  <Spec text={spec} />
                </Reveal>
              ))}
            </dl>
            <Reveal delay={0.3} className="flex items-center gap-4">
              <Button
                asChild
                size="lg"
                className="h-12 rounded-full bg-white px-7 text-zinc-950 hover:bg-white/90"
              >
                <Link href={`/shop/${p.sku}`}>
                  Explore <ArrowRight />
                </Link>
              </Button>
              <span className="text-lg font-semibold tabular-nums">
                <Price usd={p.price} />
              </span>
            </Reveal>
          </div>
          <motion.div
            initial={{ opacity: 0, rotate: -4, scale: 0.9 }}
            whileInView={{ opacity: 1, rotate: 0, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.9, ease: EASE_OUT }}
            className="rounded-3xl bg-white p-8"
          >
            <ProductImage
              url={p.images[1]?.url ?? p.images[0]?.url}
              line={p.product_line}
              alt={p.name}
              className="w-full bg-transparent"
            />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
