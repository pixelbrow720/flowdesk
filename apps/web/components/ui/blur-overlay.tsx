"use client";

import type { ReactNode } from "react";
import { cn } from "../../lib/cn";

export interface BlurOverlayProps {
  /** Content rendered ON TOP of the blur (CTAs, login, etc.). */
  children: ReactNode;
  /** Blur intensity. */
  intensity?: "sm" | "md" | "lg";
  className?: string;
}

const INTENSITY: Record<NonNullable<BlurOverlayProps["intensity"]>, string> = {
  sm: "backdrop-blur-sm",
  md: "backdrop-blur-md",
  lg: "backdrop-blur-lg",
};

/**
 * Full-cover blur scrim with centered content. Used for the NO_DESK / ANON
 * gated experience (PRD #6): the dashboard stays rendered underneath and is
 * genuinely blurred (not hidden), with CTAs layered on top.
 */
export function BlurOverlay({ children, intensity = "md", className }: BlurOverlayProps) {
  return (
    <div
      className={cn(
        "absolute inset-0 z-40 flex items-center justify-center",
        "bg-[var(--color-bg)]/40",
        INTENSITY[intensity],
        className,
      )}
    >
      {children}
    </div>
  );
}
