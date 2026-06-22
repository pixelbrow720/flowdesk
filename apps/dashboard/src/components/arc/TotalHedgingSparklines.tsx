/**
 * TotalHedgingSparklines — three side-by-side mini line charts.
 *
 * Renders the synthetic-OI #7 total-hedging map (`total_hedging` field) as a
 * 3-cell row of sparklines:
 *   - gamma_hedge (USD per 1% price move)
 *   - charm_hedge (USD dealer dollar-delta per calendar day)
 *   - vanna_hedge (USD dealer dollar-delta per 1% IV move)
 *
 * Each line is self-normalized within its panel so the SHAPE is visible
 * regardless of unit scale (the three values have different units and MUST NOT
 * share a y-scale). Turquoise when the latest value is positive, crimson when
 * negative — the locked sign convention from the contract.
 *
 * EXPERIMENTAL — not price-validated, lives alongside VOL-GEX.
 */

import { useMemo } from "react";

export interface SparklineFrame {
  minute_index: number;
  total_hedging?:
    | { gamma_hedge: number; charm_hedge: number; vanna_hedge: number }
    | null;
}

export interface TotalHedgingSparklinesProps {
  frames: SparklineFrame[];
  className?: string;
}

const SERIES: { key: "gamma_hedge" | "charm_hedge" | "vanna_hedge"; label: string; unit: string }[] = [
  { key: "gamma_hedge", label: "γ Hedge", unit: "USD / 1% move" },
  { key: "charm_hedge", label: "Charm Hedge", unit: "USD / day" },
  { key: "vanna_hedge", label: "Vanna Hedge", unit: "USD / 1% IV" },
];

const TURQUOISE = "#0FB5A8";
const CRIMSON = "#B5002E";
const BONE_3 = "#8E8E88";

export function TotalHedgingSparklines({
  frames,
  className = "flex-1",
}: TotalHedgingSparklinesProps) {
  const series = useMemo(() => {
    return SERIES.map((s) => {
      const values: { minute: number; v: number | null }[] = [];
      for (const f of frames) {
        const v = f.total_hedging ? f.total_hedging[s.key] : null;
        values.push({ minute: f.minute_index, v: Number.isFinite(v) ? (v as number) : null });
      }
      // Latest non-null value drives the sign color.
      let last: number | null = null;
      for (let i = values.length - 1; i >= 0; i--) {
        if (values[i].v !== null) {
          last = values[i].v;
          break;
        }
      }
      // Sparkline x-domain: spread over the minute range.
      const minutes = values.map((v) => v.minute);
      const minMin = minutes[0] ?? 0;
      const maxMin = minutes[minutes.length - 1] ?? 1;
      const span = Math.max(1, maxMin - minMin);
      // Y-range: span across this series' finite values (skip nulls).
      let min = Infinity;
      let max = -Infinity;
      for (const x of values) {
        if (x.v === null) continue;
        if (x.v < min) min = x.v;
        if (x.v > max) max = x.v;
      }
      if (!Number.isFinite(min) || !Number.isFinite(max)) {
        min = 0; max = 0;
      }
      // Pad so the line never sits on the edge.
      const pad = (max - min) * 0.1 || 1;
      return {
        ...s,
        last,
        values,
        minMin,
        span,
        yMin: min - pad,
        yMax: max + pad,
      };
    });
  }, [frames]);

  return (
    <div className={`grid grid-cols-3 gap-3 ${className}`}>
      {series.map((s) => {
        const color = s.last === null ? BONE_3 : s.last >= 0 ? TURQUOISE : CRIMSON;
        const w = 200; // viewBox width
        const h = 56; // viewBox height
        const padX = 4;
        const padY = 6;
        const innerW = w - padX * 2;
        const innerH = h - padY * 2;
        const yRange = Math.max(1e-12, s.yMax - s.yMin);

        // Build the polyline path, skipping null cells (gap-tolerant).
        const segments: string[] = [];
        let pendingMove = true;
        for (const v of s.values) {
          if (v.v === null) {
            pendingMove = true;
            continue;
          }
          const x = padX + ((v.minute - s.minMin) / s.span) * innerW;
          const y = padY + (1 - (v.v - s.yMin) / yRange) * innerH;
          segments.push(pendingMove ? `M${x},${y}` : `L${x},${y}`);
          pendingMove = false;
        }
        const path = segments.join(" ");
        // A series is "empty" when no finite point ever appears (e.g. REPLAY
        // sessions ship without the live-only `total_hedging` field). Show an
        // explicit note instead of a silent blank panel.
        const hasData = path.length > 0;

        const latestText =
          s.last === null
            ? "—"
            : `${s.last >= 0 ? "+" : ""}${formatCompact(s.last)}`;

        return (
          <div
            key={s.key}
            className="flex flex-col gap-1 rounded-[3px] border border-rule/40 bg-black px-3 py-2"
          >
            <div className="flex items-baseline justify-between font-mono">
              <span className="text-[10px] uppercase tracking-[0.18em] text-bone-3">
                {s.label}
              </span>
              <span
                className="text-[11px] tabular-nums"
                style={{ color }}
              >
                {latestText}
              </span>
            </div>
            {hasData ? (
              <svg
                viewBox={`0 0 ${w} ${h}`}
                preserveAspectRatio="none"
                className="h-12 w-full"
                role="img"
                aria-label={`${s.label} sparkline`}
              >
                {/* zero line (only if range straddles zero) */}
                {s.yMin < 0 && s.yMax > 0 && (
                  <line
                    x1={padX}
                    x2={w - padX}
                    y1={padY + (1 - (0 - s.yMin) / yRange) * innerH}
                    y2={padY + (1 - (0 - s.yMin) / yRange) * innerH}
                    stroke="#1E1E22"
                    strokeWidth={1}
                  />
                )}
                <path
                  d={path}
                  fill="none"
                  stroke={color}
                  strokeWidth={1.25}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              </svg>
            ) : (
              <div className="flex h-12 w-full items-center justify-center text-center font-mono text-[9px] leading-tight tracking-[0.12em] text-bone-3/45">
                live-only · absent in replay
              </div>
            )}
            <span className="font-mono text-[9px] tracking-[0.2em] text-bone-3/60">
              {s.unit}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Compact USD magnitude: e.g. 12.3M / -456K / 78.9B. */
function formatCompact(v: number): string {
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(1)}K`;
  return `${sign}${abs.toFixed(0)}`;
}