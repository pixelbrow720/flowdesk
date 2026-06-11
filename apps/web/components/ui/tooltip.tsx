"use client";

import type { ReactNode } from "react";
import { cn } from "../../lib/cn";

type Side = "top" | "bottom" | "left" | "right";

export interface TooltipProps {
  /** The hover/focus target. */
  children: ReactNode;
  /** Tooltip text. */
  content: ReactNode;
  side?: Side;
  className?: string;
}

const SIDES: Record<Side, string> = {
  top: "bottom-full left-1/2 -translate-x-1/2 mb-8",
  bottom: "top-full left-1/2 -translate-x-1/2 mt-8",
  left: "right-full top-1/2 -translate-y-1/2 mr-8",
  right: "left-full top-1/2 -translate-y-1/2 ml-8",
};

/**
 * CSS-only tooltip: shown on group hover/focus-within. Keyboard accessible —
 * the trigger should be focusable. No positioning library (kept primitive).
 */
export function Tooltip({ children, content, side = "top", className }: TooltipProps) {
  return (
    <span className={cn("group/tt relative inline-flex", className)}>
      {children}
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none absolute z-50 whitespace-nowrap rounded border border-border",
          "bg-surface px-12 py-4 font-display text-caption text-fg shadow-elevation-2",
          "opacity-0 transition-opacity duration-base ease-standard",
          "group-hover/tt:opacity-100 group-focus-within/tt:opacity-100",
          SIDES[side],
        )}
      >
        {content}
      </span>
    </span>
  );
}
