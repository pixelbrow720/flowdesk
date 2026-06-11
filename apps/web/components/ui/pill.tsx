"use client";

import type { ReactNode } from "react";
import { cn } from "../../lib/cn";

type Tone = "neutral" | "positive" | "negative";

export interface PillProps {
  children: ReactNode;
  tone?: Tone;
  /** Subtle data-state glow (used by the regime pill). */
  glow?: boolean;
  className?: string;
}

const TONES: Record<Tone, string> = {
  neutral: "bg-surface text-muted border-border",
  positive: "bg-turquoise/15 text-turquoise border-turquoise/40",
  negative: "bg-crimson/15 text-crimson border-crimson/40",
};

const GLOWS: Record<Tone, string> = {
  neutral: "",
  positive: "shadow-glow-positive",
  negative: "shadow-glow-negative",
};

/** Compact status pill. Tone colors are locked turquoise/crimson only. */
export function Pill({ children, tone = "neutral", glow = false, className }: PillProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-8 rounded-full border px-12 py-4",
        "font-display text-caption uppercase tracking-[0.04em]",
        TONES[tone],
        glow && GLOWS[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
