"use client";

import { cn } from "../../lib/cn";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

export interface SegmentedControlProps<T extends string> {
  options: ReadonlyArray<SegmentedOption<T>>;
  value: T;
  onChange: (value: T) => void;
  /** Accessible group label. */
  ariaLabel: string;
  className?: string;
}

/**
 * Segmented control (e.g. ES | NQ). Single-select, token-driven, keyboard
 * navigable via the native radiogroup roles.
 */
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
  className,
}: SegmentedControlProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center gap-4 rounded border border-border bg-surface p-4",
        className,
      )}
    >
      {options.map((opt) => {
        const selected = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(opt.value)}
            className={cn(
              "h-24 rounded px-12 font-mono text-caption tabular-nums",
              "transition-[background,color] duration-base ease-standard",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-turquoise",
              selected
                ? "bg-turquoise text-base"
                : "bg-transparent text-muted hover:text-fg",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
