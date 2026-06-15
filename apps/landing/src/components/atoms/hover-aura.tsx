"use client";

/**
 * HoverAura — brick aura inside a `group`.
 *
 * "stay"  — grows left→right on hover, holds. Cards.
 * "sweep" — passes through left→right then fades (auraSweep keyframe in globals.css).
 *           Used on horizontal rows where a persistent fill would dominate.
 */

type Variant = "stay" | "sweep";

export function HoverAura({ variant = "stay" }: { variant?: Variant }) {
  if (variant === "sweep") {
    return (
      <span
        aria-hidden
        className="aura-sweep pointer-events-none absolute inset-0 -z-10 origin-left bg-gradient-to-r from-brick/30 via-brick/12 to-transparent opacity-0"
      />
    );
  }
  return (
    <span
      aria-hidden
      className="pointer-events-none absolute inset-0 -z-10 origin-left scale-x-0 bg-gradient-to-r from-brick/22 via-brick/10 to-transparent opacity-0 transition-[transform,opacity] duration-[600ms] ease-out group-hover:scale-x-100 group-hover:opacity-100"
    />
  );
}
