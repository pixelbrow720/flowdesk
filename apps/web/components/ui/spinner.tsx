import { cn } from "../../lib/cn";

type Size = "sm" | "md";

export interface SpinnerProps {
  size?: Size;
  /** Accessible label for screen readers. */
  label?: string;
  className?: string;
}

const SIZES: Record<Size, string> = {
  sm: "h-16 w-16 border-2",
  md: "h-24 w-24 border-2",
};

/**
 * Minimal loading spinner. The animation is neutralized under
 * prefers-reduced-motion by the global rule in globals.css.
 */
export function Spinner({ size = "md", label = "Loading", className }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-label={label}
      className={cn(
        "inline-block animate-spin rounded-full border-border border-t-turquoise",
        SIZES[size],
        className,
      )}
    />
  );
}
