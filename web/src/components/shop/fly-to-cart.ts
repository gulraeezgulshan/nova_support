"use client";

import { animate } from "motion/react";

/** Sends a small brand-coloured dot from `from` to the header cart button. */
export function flyToCart(from: HTMLElement) {
  const target = document.getElementById("cart-button");
  if (!target || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const a = from.getBoundingClientRect();
  const b = target.getBoundingClientRect();
  const size = 16;
  const dot = document.createElement("div");
  Object.assign(dot.style, {
    position: "fixed",
    left: `${a.left + a.width / 2 - size / 2}px`,
    top: `${a.top + a.height / 2 - size / 2}px`,
    width: `${size}px`,
    height: `${size}px`,
    borderRadius: "9999px",
    background: "var(--brand)",
    boxShadow: "0 0 0 4px color-mix(in oklch, var(--brand) 25%, transparent)",
    zIndex: "60",
    pointerEvents: "none",
  });
  document.body.appendChild(dot);
  const dx = b.left + b.width / 2 - (a.left + a.width / 2);
  const dy = b.top + b.height / 2 - (a.top + a.height / 2);
  animate(
    dot,
    { x: [0, dx], y: [0, dy], scale: [1, 0.5], opacity: [1, 0.7] },
    {
      duration: 0.75,
      x: { duration: 0.75, ease: [0.25, 0.1, 0.25, 1] },
      y: { duration: 0.75, ease: [0.6, -0.4, 0.7, 0.3] },
    },
  ).then(() => dot.remove());
}
