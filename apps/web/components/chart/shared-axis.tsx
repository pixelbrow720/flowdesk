"use client";

import { useMemo } from "react";
import type { YScale } from "../../lib/scale";

export interface SharedAxisProps {
  scale: YScale;
  /** Current forward price -> dashed line + single tag. */
  forward: number;
  /** Pixel width of the axis column (~72px per PRD #4). */
  width: number;
  className?: string;
}

/**
 * The single centered strike/price axis shared by the profile (left) and the
 * heatmap (right). Owns nothing about the data — only renders tick labels from
 * the shared Y-scale and the dashed current-price line with ONE price tag.
 * Labels every `step` points (5 for ES, 10 for NQ). All numbers JetBrains Mono.
 */
export function SharedAxis({ scale, forward, width, className }: SharedAxisProps) {
  const ticks = useMemo(() => scale.ticks(), [scale]);
  const priceY = scale.yOf(forward);

  // Thin out labels so they never collide: keep ~16px min spacing.
  const minGap = 16;
  const labelStep = Math.max(
    1,
    Math.ceil(minGap / (scale.height / Math.max(1, ticks.length - 1))),
  );

  return (
    <div
      className={`relative h-full ${className ?? ""}`}
      style={{ width }}
      aria-hidden={false}
      role="img"
      aria-label="Strike price axis"
    >
      {/* tick labels */}
      {ticks.map((t, i) => {
        if (i % labelStep !== 0) return null;
        const y = scale.yOf(t);
        return (
          <span
            key={t}
            className="absolute left-1/2 -translate-x-1/2 -translate-y-1/2 font-mono text-[10px] tabular-nums text-muted"
            style={{ top: y }}
          >
            {t}
          </span>
        );
      })}

      {/* dashed current-price line spanning the axis column, with one tag */}
      <div
        className="pointer-events-none absolute left-0 right-0 border-t border-dashed border-fg/70"
        style={{ top: priceY }}
      />
      <span
        className="absolute left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-sm border border-fg/30 bg-surface px-4 py-2 font-mono text-[10px] tabular-nums text-fg"
        style={{ top: priceY }}
      >
        {forward.toFixed(2)}
      </span>
    </div>
  );
}
