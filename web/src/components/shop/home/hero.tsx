"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, RotateCcw, ShieldCheck, Truck } from "lucide-react";
import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import Link from "next/link";
import { useRef } from "react";

import { EASE_OUT } from "@/components/motion/reveal";
import { ProductImage } from "@/components/shop/product-image";
import { Button } from "@/components/ui/button";
import { getProductOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import { formatMoney } from "@/lib/format";
import { useStorefront } from "@/lib/storefront";

const HERO_SKU = "VH-LAP-AB14";
const HEADLINE = ["Electronics", "that", "just", "work."];

export function Hero() {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const imageY = useTransform(scrollYProgress, [0, 1], [0, 90]);
  const textY = useTransform(scrollYProgress, [0, 1], [0, 40]);
  const still = useReducedMotion(); // scroll-linked styles ignore MotionConfig

  const product = useQuery(getProductOptions({ path: { sku: HERO_SKU } }));
  const config = useStorefront().data;

  const trust = config
    ? [
        { icon: Truck, text: `Express delivery in ${config.shipping.express_days} business days` },
        { icon: RotateCcw, text: `${config.returns.window_days}-day returns` },
        { icon: ShieldCheck, text: `${config.warranty.months}-month warranty` },
      ]
    : [];

  return (
    <section ref={ref} className="relative -mt-16 overflow-hidden pt-16">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top_right,var(--brand-soft),transparent_60%)]" />
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-full bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] [mask-image:radial-gradient(ellipse_at_center,black_20%,transparent_70%)] bg-[size:48px_48px] opacity-40" />
      <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 py-16 md:py-24 lg:grid-cols-2">
        <motion.div style={still ? undefined : { y: textY }} className="space-y-7">
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: EASE_OUT }}
            className="inline-flex items-center gap-2 rounded-full border bg-background/70 px-3 py-1 text-xs font-medium backdrop-blur"
          >
            <span className="size-1.5 rounded-full bg-brand" />
            New season · AeroBook 14 is here
          </motion.p>
          <h1 className="text-5xl font-semibold tracking-tighter text-balance sm:text-6xl lg:text-7xl">
            {HEADLINE.map((word, i) => (
              <span key={word} className="inline-block overflow-hidden pr-[0.25em] align-bottom">
                <motion.span
                  className={i === 3 ? "inline-block text-brand" : "inline-block"}
                  initial={{ y: "110%" }}
                  animate={{ y: 0 }}
                  transition={{ duration: 0.8, ease: EASE_OUT, delay: 0.1 + i * 0.08 }}
                >
                  {word}
                </motion.span>
              </span>
            ))}
          </h1>
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE_OUT, delay: 0.45 }}
            className="max-w-lg text-lg text-muted-foreground"
          >
            Phones, laptops, audio and smart home, chosen for quality. And if anything ever goes
            wrong, our support team and assistant are one click away.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE_OUT, delay: 0.55 }}
            className="flex flex-wrap gap-3"
          >
            <Button
              asChild
              size="lg"
              className="h-12 rounded-full bg-brand px-7 text-brand-foreground shadow-lg shadow-brand/25 hover:bg-brand/90"
            >
              <Link href="/shop">
                Shop now <ArrowRight />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="h-12 rounded-full px-7">
              <Link href={`/shop/${HERO_SKU}`}>Meet the AeroBook</Link>
            </Button>
          </motion.div>
          <motion.ul
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.75 }}
            className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground"
          >
            {trust.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-2">
                <Icon className="size-4 text-brand" /> {text}
              </li>
            ))}
          </motion.ul>
        </motion.div>
        <motion.div
          style={still ? undefined : { y: imageY }}
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.9, ease: EASE_OUT, delay: 0.2 }}
          className="relative mx-auto w-full max-w-lg"
        >
          <div className="absolute inset-10 -z-10 rounded-full bg-brand/30 blur-3xl" />
          <motion.div
            animate={{ y: [0, -14, 0] }}
            transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            className="rounded-[2rem] border bg-white/80 p-8 shadow-2xl shadow-brand/10 backdrop-blur dark:bg-card/80"
          >
            <ProductImage
              url={product.data?.images[0]?.url}
              line="LAPTOP"
              alt={product.data?.name ?? "AeroBook 14 laptop"}
              className="w-full bg-transparent"
            />
          </motion.div>
          {product.data ? (
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, ease: EASE_OUT, delay: 0.9 }}
              className="absolute -bottom-4 -left-2 rounded-2xl border bg-background/90 px-4 py-3 shadow-xl backdrop-blur sm:-left-8"
            >
              <p className="text-xs text-muted-foreground">{product.data.name}</p>
              <p className="text-lg font-semibold tabular-nums">
                {formatMoney(product.data.price)}
              </p>
            </motion.div>
          ) : null}
        </motion.div>
      </div>
    </section>
  );
}
