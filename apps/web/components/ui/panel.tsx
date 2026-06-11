"use client";

import { forwardRef, type HTMLAttributes, type ReactNode } from "react";
import { cn } from "../../lib/cn";

type Variant = "surface" | "glass";

export interface PanelProps extends HTMLAttributes<HTMLDivElement> {
  variant?: Variant;
  children: ReactNode;
}

const VARIANTS: Record<Variant, string> = {
  // Opaque panel chrome (topbar, settings, cards).
  surface: "bg-surface border border-border",
  // Glassmorphism-lite for floating overlays (toolbar). Subtle, not cheesy.
  glass:
    "border border-border bg-[var(--color-surface)]/70 backdrop-blur-md backdrop-saturate-150",
};

/** Generic surface container. Token-driven; no hard-coded color. */
export const Panel = forwardRef<HTMLDivElement, PanelProps>(
  ({ variant = "surface", className, children, ...rest }, ref) => (
    <div
      ref={ref}
      className={cn("rounded-lg", VARIANTS[variant], className)}
      {...rest}
    >
      {children}
    </div>
  ),
);
Panel.displayName = "Panel";
