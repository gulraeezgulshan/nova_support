"use client";

import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useMemo, useState } from "react";

import { currencyRatesOptions } from "@/lib/api/generated/@tanstack/react-query.gen";

const COOKIE = "currency";
const DIGITS: Record<string, number> = { USD: 2, PKR: 0, EUR: 2, GBP: 2, AED: 2 };
const SYMBOLS: Record<string, string> = { USD: "$", PKR: "Rs", EUR: "€", GBP: "£", AED: "AED" };

function readCookie(): string {
  if (typeof document === "undefined") return "USD";
  const match = document.cookie.match(/(?:^|; )currency=([A-Z]{3})/);
  return match?.[1] ?? "USD";
}

export function money(amount: number, code: string): string {
  const digits = DIGITS[code] ?? 2;
  const n = amount.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return code === "USD" ? `$${n}` : `${SYMBOLS[code] ?? code} ${n}`;
}

type Ctx = {
  code: string;
  setCode: (code: string) => void;
  format: (usd: number) => string;
  codes: string[];
};
const CurrencyContext = createContext<Ctx | null>(null);

export function CurrencyProvider({ children }: { children: React.ReactNode }) {
  const [code, setState] = useState(readCookie);
  const rates = useQuery({ ...currencyRatesOptions(), staleTime: 60 * 60 * 1000 });
  const value = useMemo<Ctx>(() => {
    const table = rates.data?.rates ?? { USD: 1 };
    const active = table[code] ? code : "USD"; // no rate yet: show USD
    return {
      code: active,
      codes: Object.keys(table),
      setCode: (next) => {
        document.cookie = `${COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
        setState(next);
      },
      format: (usd) => money(usd * (table[active] ?? 1), active),
    };
  }, [code, rates.data]);
  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>;
}

export function useCurrency(): Ctx {
  const ctx = useContext(CurrencyContext);
  return (
    ctx ?? { code: "USD", codes: ["USD"], setCode: () => {}, format: (usd) => money(usd, "USD") }
  );
}

export function Price({ usd, className }: { usd: number; className?: string }) {
  return <span className={className}>{useCurrency().format(usd)}</span>;
}

/** What the customer paid, in the currency they saw at checkout. */
export function formatLocal(order: {
  amount: number;
  currency: string;
  amount_local?: number | null;
}): string {
  return money(
    order.amount_local ?? order.amount,
    order.amount_local == null ? "USD" : order.currency,
  );
}
