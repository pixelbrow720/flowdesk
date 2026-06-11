"use client";

import { useDashboardStore } from "../../lib/store";
import { NumberReadout } from "../ui/number-readout";
import { cn } from "../../lib/cn";

export interface RegimeBarProps {
  className?: string;
}

/**
 * Regime indicator (PRD #4): a BAR/PILL — explicitly NOT a speedometer/gauge.
 * Color follows the sign of net gamma: positive => PINNING (turquoise),
 * negative => VOLATILE (crimson), flat => neutral. A horizontal fill encodes
 * the stability %, rendered as a number in JetBrains Mono.
 *
 * All values come from snapshot.regime.
 */
export function RegimeBar({ className }: RegimeBarProps) {
  const regime = useDashboardStore((s) => s.snapshot.regime);
  const positive = regime.sign > 0;
  const negative = regime.sign < 0;
  const label = positive ? "PINNING" : negative ? "VOLATILE" : "NEUTRAL";
  const fill = Math.max(0, Math.min(100, regime.stability_pct));

  const accent = positive ? "bg-turquoise" : negative ? "bg-crimson" : "bg-muted";
  const text = positive ? "text-turquoise" : negative ? "text-crimson" : "text-muted";

  return (
    <div
      className={cn(
        "inline-flex items-center gap-12 rounded-full border border-border bg-surface px-12 py-4",
        className,
      )}
      role="status"
      aria-label={`Regime ${label}, stability ${fill.toFixed(1)} percent`}
    >
      <span
        className={cn(
          "font-display text-caption font-medium uppercase tracking-[0.06em]",
          text,
        )}
      >
        {label}
      </span>

      {/* horizontal stability bar (NOT a gauge) */}
      <span className="relative h-8 w-64 overflow-hidden rounded-full bg-border">
        <span
          className={cn("absolute inset-y-0 left-0 rounded-full", accent)}
          style={{ width: `${fill}%` }}
        />
      </span>

      <span className="flex items-baseline gap-2">
        <NumberReadout value={fill} decimals={1} suffix="%" size="sm" />
      </span>
    </div>
  );
}
