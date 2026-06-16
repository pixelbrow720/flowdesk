/**
 * StatTile — small number block. Variants:
 *   - delta="pct": signed % (e.g. +0.42 → "+0.42%")
 *   - delta="bn": signed billion delta (e.g. +1.8 → "+$1.8B")
 *   - secondary: extra small label below primary
 */

type Props = {
  label: string;
  primary: string;
  delta?: number;
  deltaFmt?: "pct" | "bn";
  secondary?: string;
  className?: string;
};

export function StatTile({
  label,
  primary,
  delta,
  deltaFmt,
  secondary,
  className = "",
}: Props) {
  const deltaStr =
    delta === undefined
      ? null
      : deltaFmt === "pct"
        ? `${delta >= 0 ? "+" : "−"}${Math.abs(delta).toFixed(2)}%`
        : `${delta >= 0 ? "+" : "−"}$${Math.abs(delta).toFixed(1)}B`;
  const deltaColor =
    delta === undefined ? "" : delta >= 0 ? "text-bone-1" : "text-brick-glow";

  return (
    <div
      className={`border border-[color:var(--hairline)] p-4 flex flex-col justify-between ${className}`}
    >
      <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3">
        {label}
      </span>
      <div className="flex items-baseline gap-2 mt-2">
        <span className="font-mono text-[24px] tabular-nums text-bone-0 leading-none">
          {primary}
        </span>
        {deltaStr && (
          <span
            className={`font-mono text-[11px] tabular-nums ${deltaColor}`}
          >
            {deltaStr}
          </span>
        )}
      </div>
      {secondary && (
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-bone-3 mt-1">
          {secondary}
        </span>
      )}
    </div>
  );
}

export default StatTile;
