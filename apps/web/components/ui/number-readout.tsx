import { cn } from "../../lib/cn";

type Size = "sm" | "md" | "lg";

export interface NumberReadoutProps {
  /** The numeric value to render. */
  value: number;
  /** Decimal places (fixed). Default 2. */
  decimals?: number;
  /** Optional unit/suffix (e.g. "%", "$"). Rendered in muted weight. */
  suffix?: string;
  /** Optional prefix (e.g. "$"). */
  prefix?: string;
  /** Color by sign: positive turquoise, negative crimson. Off by default. */
  colorBySign?: boolean;
  /** Compact large numbers as K/M/B. */
  compact?: boolean;
  size?: Size;
  className?: string;
}

const SIZES: Record<Size, string> = {
  sm: "text-caption",
  md: "text-mono",
  lg: "text-h2",
};

function format(value: number, decimals: number, compact: boolean): string {
  if (compact) {
    const abs = Math.abs(value);
    const units: Array<[number, string]> = [
      [1e9, "B"],
      [1e6, "M"],
      [1e3, "K"],
    ];
    for (const [scale, suf] of units) {
      if (abs >= scale) return `${(value / scale).toFixed(1)}${suf}`;
    }
  }
  return value.toFixed(decimals);
}

/**
 * Canonical numeric figure. ALL numbers in the UI must render through this
 * (JetBrains Mono + tabular-nums) per the locked contract. Optional signed
 * coloring uses only the locked turquoise/crimson tokens.
 */
export function NumberReadout({
  value,
  decimals = 2,
  suffix,
  prefix,
  colorBySign = false,
  compact = false,
  size = "md",
  className,
}: NumberReadoutProps) {
  const signColor = !colorBySign
    ? "text-fg"
    : value > 0
      ? "text-turquoise"
      : value < 0
        ? "text-crimson"
        : "text-muted";

  return (
    <span
      className={cn(
        "font-mono tabular-nums tracking-tight",
        SIZES[size],
        signColor,
        className,
      )}
    >
      {prefix && <span className="text-muted">{prefix}</span>}
      {format(value, decimals, compact)}
      {suffix && <span className="ml-[2px] text-muted">{suffix}</span>}
    </span>
  );
}
