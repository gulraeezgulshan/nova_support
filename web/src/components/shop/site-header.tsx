"use client";

import { Show, SignInButton, UserButton, useAuth } from "@clerk/nextjs";

import { BrandMark, useBranding } from "@/lib/branding";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Menu, ShoppingBag } from "lucide-react";
import { AnimatePresence, motion, useMotionValueEvent, useScroll } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { useCart } from "@/components/shop/cart-context";
import { PRODUCT_LINES } from "@/components/shop/lines";
import { ShopMegaMenu } from "@/components/shop/mega-menu";
import { MiniCart } from "@/components/shop/mini-cart";
import { SearchBox } from "@/components/shop/search-box";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { readMeOptions } from "@/lib/api/generated/@tanstack/react-query.gen";
import { openCart, openChat } from "@/lib/storefront";
import { cn } from "@/lib/utils";

const SUPPORT_LINKS = [
  { href: "/help", label: "Help centre" },
  { href: "/orders", label: "Track an order" },
  { href: "/contact", label: "Contact us" },
];

export function Logo({ className }: { className?: string }) {
  const name = useBranding().data?.shop_name?.split(" ")[0] ?? "VoltHaven";
  return (
    <Link
      href="/"
      className={cn("flex items-center gap-2 font-semibold tracking-tight", className)}
    >
      <BrandMark target="shop" />
      <span className="text-lg">{name}</span>
    </Link>
  );
}

export function SiteHeader() {
  const { count } = useCart();
  const { isSignedIn } = useAuth();
  const me = useQuery({ ...readMeOptions(), enabled: Boolean(isSignedIn) });
  const staff = me.data && me.data.role !== "customer";
  const pathname = usePathname();
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const { scrollY } = useScroll();
  useMotionValueEvent(scrollY, "change", (y) => setScrolled(y > 8));
  const clear = pathname === "/" && !scrolled; // blends into the home hero until you scroll

  return (
    <header
      className={cn(
        "sticky top-0 z-40 border-b transition-[background-color,border-color,box-shadow] duration-300",
        clear
          ? "border-transparent bg-transparent"
          : "border-border/60 bg-background/80 shadow-sm backdrop-blur-xl",
      )}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-2 px-4 sm:gap-4">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          aria-label="Open menu"
          onClick={() => setMenuOpen(true)}
        >
          <Menu />
        </Button>
        <Logo />
        <nav className="ml-4 hidden items-center gap-1 text-sm md:flex">
          <ShopMegaMenu />
          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="gap-1">
                Support <ChevronDown className="size-3.5 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" sideOffset={10} className="w-52">
              {SUPPORT_LINKS.map((l) => (
                <DropdownMenuItem key={l.href} asChild>
                  <Link href={l.href}>{l.label}</Link>
                </DropdownMenuItem>
              ))}
              <DropdownMenuItem onSelect={() => openChat()}>Chat with us</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button asChild variant="ghost" size="sm">
            <Link href="/about">About</Link>
          </Button>
        </nav>
        <SearchBox className="ml-auto hidden w-64 lg:block" />
        <div className="ml-auto flex items-center gap-1 lg:ml-0">
          {staff ? (
            <Button asChild variant="outline" size="sm" className="hidden sm:inline-flex">
              <Link href="/dashboard">Staff console</Link>
            </Button>
          ) : null}
          <Show when="signed-in">
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
              <Link href="/orders">My orders</Link>
            </Button>
          </Show>
          <Button
            id="cart-button"
            variant="ghost"
            size="icon"
            className="relative"
            aria-label={`Cart, ${count} items`}
            onClick={openCart}
          >
            <ShoppingBag />
            <AnimatePresence>
              {count ? (
                <motion.span
                  key={count}
                  initial={{ scale: 0.4, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ type: "spring", stiffness: 500, damping: 18 }}
                  className="absolute -top-0.5 -right-0.5 flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-brand px-1 text-[10px] font-semibold text-brand-foreground tabular-nums"
                >
                  {count}
                </motion.span>
              ) : null}
            </AnimatePresence>
          </Button>
          <Show when="signed-in">
            <UserButton />
          </Show>
          <Show when="signed-out">
            <SignInButton>
              <Button size="sm" className="rounded-full">
                Sign in
              </Button>
            </SignInButton>
          </Show>
        </div>
      </div>
      <MiniCart />
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="w-80">
          <SheetHeader>
            <SheetTitle>Menu</SheetTitle>
          </SheetHeader>
          <div className="flex flex-col gap-6 overflow-y-auto px-4 pb-6">
            <SearchBox onDone={() => setMenuOpen(false)} />
            <MobileSection title="Shop">
              <MobileLink href="/shop" onClick={() => setMenuOpen(false)}>
                All products
              </MobileLink>
              {PRODUCT_LINES.map((l) => (
                <MobileLink
                  key={l.code}
                  href={`/shop?line=${l.code}`}
                  onClick={() => setMenuOpen(false)}
                >
                  {l.label}
                </MobileLink>
              ))}
            </MobileSection>
            <MobileSection title="Support">
              {SUPPORT_LINKS.map((l) => (
                <MobileLink key={l.href} href={l.href} onClick={() => setMenuOpen(false)}>
                  {l.label}
                </MobileLink>
              ))}
              <button
                type="button"
                className="rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
                onClick={() => {
                  setMenuOpen(false);
                  openChat();
                }}
              >
                Chat with us
              </button>
            </MobileSection>
            <MobileSection title="Company">
              <MobileLink href="/about" onClick={() => setMenuOpen(false)}>
                About VoltHaven
              </MobileLink>
              {staff ? (
                <MobileLink href="/dashboard" onClick={() => setMenuOpen(false)}>
                  Staff console
                </MobileLink>
              ) : null}
            </MobileSection>
          </div>
        </SheetContent>
      </Sheet>
    </header>
  );
}

function MobileSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="px-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {title}
      </p>
      <div className="flex flex-col">{children}</div>
    </div>
  );
}

function MobileLink({
  href,
  onClick,
  children,
}: {
  href: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Link href={href} onClick={onClick} className="rounded-md px-2 py-1.5 text-sm hover:bg-muted">
      {children}
    </Link>
  );
}
