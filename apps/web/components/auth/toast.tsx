"use client";

import { useEffect } from "react";
import { cn } from "../../lib/cn";

export type ToastTone = "info" | "success" | "error";

export interface ToastProps {
  open: boolean;
  message: string;
  tone?: ToastTone;
  /** Auto-dismiss after ms (0 = sticky). Default 3000. */
  autoHideMs?: number;
  onClose?: () => void;
}

const TONES: Record<ToastTone, string> = {
  info: "border-border text-fg",
  success: "border-turquoise/40 text-turquoise",
  error: "border-crimson/40 text-crimson",
};

/**
 * Bottom-center toast for transient feedback (e.g. the re-check result). Uses
 * role=status (aria-live polite) so screen readers announce it. Auto-dismisses
 * unless `autoHideMs` is 0.
 */
export function Toast({ open, message, tone = "info", autoHideMs = 3000, onClose }: ToastProps) {
  useEffect(() => {
    if (!open || autoHideMs <= 0) return;
    const id = setTimeout(() => onClose?.(), autoHideMs);
    return () => clearTimeout(id);
  }, [open, autoHideMs, onClose]);

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "pointer-events-none fixed bottom-24 left-1/2 z-[60] -translate-x-1/2",
        "transition-opacity duration-base ease-standard",
        open ? "opacity-100" : "opacity-0",
      )}
    >
      {open && (
        <div
          className={cn(
            "rounded-lg border bg-surface px-16 py-12 font-display text-caption shadow-elevation-2",
            TONES[tone],
          )}
        >
          {message}
        </div>
      )}
    </div>
  );
}
