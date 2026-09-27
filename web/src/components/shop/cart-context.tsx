"use client";

import { createContext, useCallback, useContext, useMemo, useSyncExternalStore } from "react";

export type CartLine = { sku: string; quantity: number };
type Cart = {
  lines: CartLine[];
  add: (sku: string, quantity?: number) => void;
  setQuantity: (sku: string, quantity: number) => void;
  remove: (sku: string) => void;
  removeMany: (skus: string[]) => void;
  clear: () => void;
  count: number;
};

export const MAX_QUANTITY = 5; // checkout accepts at most 5 of a product
const KEY = "volthaven-cart";
const CHANGED = "volthaven-cart-changed";
const CartContext = createContext<Cart | null>(null);

function snapshot(): string {
  try {
    return localStorage.getItem(KEY) ?? "[]";
  } catch {
    return "[]"; // storage unavailable (private mode, previews)
  }
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("storage", onChange); // other tabs
  window.addEventListener(CHANGED, onChange); // this tab
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(CHANGED, onChange);
  };
}

function parse(raw: string): CartLine[] {
  try {
    const value: unknown = JSON.parse(raw);
    return Array.isArray(value) ? (value as CartLine[]) : [];
  } catch {
    return [];
  }
}

export function CartProvider({ children }: { children: React.ReactNode }) {
  const raw = useSyncExternalStore(subscribe, snapshot, () => "[]");
  const lines = useMemo(() => parse(raw), [raw]);
  const save = useCallback((next: CartLine[]) => {
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* storage unavailable: the cart cannot persist */
    }
    window.dispatchEvent(new Event(CHANGED));
  }, []);
  const value = useMemo<Cart>(
    () => ({
      lines,
      add: (sku, quantity = 1) => {
        const existing = lines.find((l) => l.sku === sku);
        save(
          existing
            ? lines.map((l) =>
                l.sku === sku
                  ? { ...l, quantity: Math.min(MAX_QUANTITY, l.quantity + quantity) }
                  : l,
              )
            : [...lines, { sku, quantity: Math.min(MAX_QUANTITY, quantity) }],
        );
      },
      setQuantity: (sku, quantity) =>
        save(
          lines.map((l) =>
            l.sku === sku ? { ...l, quantity: Math.max(1, Math.min(MAX_QUANTITY, quantity)) } : l,
          ),
        ),
      remove: (sku) => save(lines.filter((l) => l.sku !== sku)),
      removeMany: (skus) => save(lines.filter((l) => !skus.includes(l.sku))),
      clear: () => save([]),
      count: lines.reduce((n, l) => n + l.quantity, 0),
    }),
    [lines, save],
  );
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): Cart {
  const cart = useContext(CartContext);
  if (!cart) throw new Error("useCart must be used inside CartProvider");
  return cart;
}
