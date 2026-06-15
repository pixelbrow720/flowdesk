"use client";

import { useMemo } from "react";
import { useDashboardStore } from "../../lib/store";
import { candleWindow } from "../../lib/heatmap/field-2d";

export interface HiroLineProps {
  className?: string;
}

/**
 * Theme-neutral muted token. The line MUST NOT use TURQUOISE / CRIMSON: those
 * encode stabilising/destabilising GEX semantics, and HIRO sign means buy/sell
 * pressure (different physics) — coloring it red/green would semantically
 * conflict with the heatmap & walls. Mirrors the `var(--color-text-primary)`
 * pattern already used on line 189 of heatmap-overlay.tsx.
 */
const FG_MUTED = "var(--color-text-muted)";

/**
 * HIRO cumulative dealer hedging flow, rendered as a thin line OVER the
 * heatmap, sharing its time-axis with its OWN right-side $-notional axis.
 *
 * Layout MUST match heatmap-overlay.tsx's candle column placement exactly so
 * each HIRO sample sits on top of the bin whose CLOSE frame produced it:
 * `candleWindow(...)` -> `bins`, x = ((k + 0.5) / totalCols) * 100. The right
 * 25% of the panel stays empty (margin) — same as the candles.
 *
 * Renders ONLY `hiro.total` (PRD MVP). The breakdown view (calls/puts/zerodte/
 * retail) is P3, behind a future toggle.
 *
 * Empty / null handling:
 *   - all values null  -> render nothing (no "unavailable" text, no error).
 *   - some values null -> break the polyline at each gap (no fake interp).
 *   - all values zero  -> still render a flat line at y = 0 of the scale.
 */
export function HiroLine({ className }: HiroLineProps) {
  const mode = useDashboardStore((s) => s.mode);
  const frames = useDashboardStore((s) => s.frames);
  const frameIndex = useDashboardStore((s) => s.frameIndex);
  const candleSize = useDashboardStore((s) => s.candleSize);

  const plot = useMemo(() => {
    if (mode !== "REPLAY" || frames.length === 0) {
      return { paths: [] as string[], min: 0, max: 0, hasAny: false };
    }
    const { bins, totalCols } = candleWindow(frames.length, frameIndex, candleSize);
    if (bins.length === 0) {
      return { paths: [], min: 0, max: 0, hasAny: false };
    }

    // Sample HIRO.total at each bin's CLOSE frame (bin[1] = end index).
    type Pt = { x: number; v: number } | null;
    const samples: Pt[] = bins.map(([, end], k) => {
      const f = frames[end];
      const v = f?.hiro?.total;
      if (v === undefined || v === null || !Number.isFinite(v)) return null;
      return { x: ((k + 0.5) / totalCols) * 100, v };
    });

    const present = samples.filter((s): s is { x: number; v: number } => s !== null);
    if (present.length === 0) {
      return { paths: [], min: 0, max: 0, hasAny: false };
    }

    let min = Infinity;
    let max = -Infinity;
    for (const p of present) {
      if (p.v < min) min = p.v;
      if (p.v > max) max = p.v;
    }
    // 5% padding so the polyline never touches the top/bottom edge. Always
    // include 0 in the range so the right-axis "0" tick lands meaningfully.
    if (min === max) {
      // All-zero (or all-equal) case: pin a symmetric tiny window so the line
      // renders as a flat midline instead of NaN-mapping.
      const eps = Math.max(1, Math.abs(min) || 1);
      min -= eps;
      max += eps;
    } else {
      const pad = (max - min) * 0.05;
      min -= pad;
      max += pad;
      if (min > 0) min = 0;
      if (max < 0) max = 0;
    }

    const span = max - min || 1;
    // Higher value -> SVG y closer to 0 (top). preserveAspectRatio=none stretches.
    const yPct = (v: number) => (1 - (v - min) / span) * 100;

    // Break the polyline at every null gap.
    const paths: string[] = [];
    let cur: string[] = [];
    for (const s of samples) {
      if (s === null) {
        if (cur.length > 1) paths.push("M " + cur.join(" L "));
        cur = [];
        continue;
      }
      cur.push(`${s.x.toFixed(3)},${yPct(s.v).toFixed(3)}`);
    }
    if (cur.length > 1) paths.push("M " + cur.join(" L "));
    // A single-point segment: emit a tiny horizontal stub so it's still visible.
    else if (cur.length === 1) paths.push("M " + cur[0] + " L " + cur[0]);

    return { paths, min, max, hasAny: true };
  }, [mode, frames, frameIndex, candleSize]);

  if (!plot.hasAny) return null;

  // Right-axis ticks: 4 evenly-spaced ticks across [min, max], formatted in
  // billions ($B) with sign. The right ~25% of the panel is empty heatmap
  // margin — that's where we draw the axis text so it doesn't obscure data.
  const tickCount = 4;
  const ticks: { y: number; label: string }[] = [];
  for (let i = 0; i < tickCount; i++) {
    const t = i / (tickCount - 1);
    const v = plot.max - t * (plot.max - plot.min); // top = max, bottom = min
    ticks.push({ y: t * 100, label: formatNotional(v) });
  }

  return (
    <div
      className={`pointer-events-none absolute inset-0 ${className ?? ""}`}
      role="img"
      aria-label="HIRO cumulative dealer hedging flow, dollars notional"
    >
      <svg
        className="absolute inset-0 h-full w-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden
      >
        {plot.paths.map((d, i) => (
          <path
            key={i}
            d={d}
            fill="none"
            stroke={FG_MUTED}
            strokeOpacity={0.85}
            strokeWidth={1.5}
            vectorEffect="non-scaling-stroke"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}
      </svg>

      {/* Right-axis tick labels rendered as DOM (NOT inside the stretched SVG)
          so the text stays legible at any container aspect ratio. Positioned
          inside the right 25% margin band kept empty by candleWindow. */}
      {ticks.map((t, i) => (
        <div
          key={i}
          className="absolute -translate-y-1/2 font-mono text-[9px] tabular-nums"
          style={{
            top: `${t.y}%`,
            right: "4px",
            color: FG_MUTED,
            opacity: 0.85,
          }}
        >
          {t.label}
        </div>
      ))}
    </div>
  );
}

/**
 * Format a $-notional value as a signed $B (billion) string. Examples:
 *   1_200_000_000  -> "+1.2B"
 *  -3_400_000_000  -> "-3.4B"
 *             0    -> "0"
 *      450_000_000 -> "+0.5B"
 * Falls back to scientific-ish "<0.1B" for very small non-zero magnitudes so a
 * tick never reads as a misleading "+0.0B".
 */
function formatNotional(v: number): string {
  if (!Number.isFinite(v)) return "—";
  if (v === 0) return "0";
  const sign = v > 0 ? "+" : "-";
  const mag = Math.abs(v) / 1e9;
  if (mag < 0.1) return `${sign}<0.1B`;
  return `${sign}${mag.toFixed(1)}B`;
}
