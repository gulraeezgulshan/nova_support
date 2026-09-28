import { cn } from "@/lib/utils";

/** Nova, the VoltHaven support assistant: a friendly robot face in the brand colour. */
export function NovaAvatar({ className, title }: { className?: string; title?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      className={cn("shrink-0", className)}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      {title ? <title>{title}</title> : null}
      {/* antenna with a charging spark */}
      <line x1="32" y1="13" x2="32" y2="6" stroke="var(--brand)" strokeWidth="3" />
      <circle cx="32" cy="5" r="4" fill="#fbbf24" className="nova-spark" />
      {/* ears */}
      <rect x="3" y="28" width="7" height="14" rx="3.5" fill="var(--brand)" opacity="0.75" />
      <rect x="54" y="28" width="7" height="14" rx="3.5" fill="var(--brand)" opacity="0.75" />
      {/* head with a soft highlight */}
      <rect x="8" y="12" width="48" height="44" rx="19" fill="var(--brand)" />
      <ellipse cx="22" cy="20" rx="10" ry="5" fill="#fff" opacity="0.18" />
      {/* face screen */}
      <rect x="14" y="21" width="36" height="27" rx="12" fill="#eef4ff" />
      {/* eyes (blink) */}
      <g className="nova-eyes">
        <ellipse cx="25" cy="33" rx="3.3" ry="4.2" fill="#1e2a4a" />
        <ellipse cx="39" cy="33" rx="3.3" ry="4.2" fill="#1e2a4a" />
        <circle cx="26.2" cy="31.4" r="1.1" fill="#fff" />
        <circle cx="40.2" cy="31.4" r="1.1" fill="#fff" />
      </g>
      {/* cheeks and smile */}
      <circle cx="19.5" cy="39.5" r="2.6" fill="#fb7185" opacity="0.45" />
      <circle cx="44.5" cy="39.5" r="2.6" fill="#fb7185" opacity="0.45" />
      <path
        d="M26.5 40.5 Q32 45.5 37.5 40.5"
        fill="none"
        stroke="#1e2a4a"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
    </svg>
  );
}
