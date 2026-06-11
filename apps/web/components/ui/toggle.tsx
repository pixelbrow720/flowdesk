"use client";

import { cn } from "../../lib/cn";

export interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  /** When true, hides the visible label but keeps it accessible. */
  hideLabel?: boolean;
  disabled?: boolean;
  className?: string;
}

/** Token-driven switch. Turquoise when on; respects reduced-motion globally. */
export function Toggle({
  checked,
  onChange,
  label,
  hideLabel = false,
  disabled = false,
  className,
}: ToggleProps) {
  return (
    <label
      className={cn(
        "inline-flex items-center gap-8 select-none",
        disabled ? "cursor-not-allowed opacity-40" : "cursor-pointer",
        className,
      )}
    >
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={hideLabel ? label : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-16 w-32 shrink-0 rounded-full border border-border",
          "transition-[background] duration-base ease-standard",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-turquoise",
          checked ? "bg-turquoise" : "bg-surface",
        )}
      >
        <span
          className={cn(
            "absolute top-1/2 h-12 w-12 -translate-y-1/2 rounded-full bg-base",
            "transition-[left] duration-base ease-standard",
            checked ? "left-[18px]" : "left-[2px]",
          )}
        />
      </button>
      {!hideLabel && (
        <span className="font-display text-caption text-fg">{label}</span>
      )}
    </label>
  );
}
