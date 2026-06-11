"use client";

import { useMemo } from "react";
import { useDashboardStore } from "../../lib/store";
import { candleWindow } from "../../lib/heatmap/field-2d";
import { NumberReadout } from "../ui/number-readout";

export interface HeatmapOverlayProps {
  /** Strike grid of the rendered field (low -> high), for strike->y mapping. */
  priceGrid: number[];
  className?: string;
}

const TURQUOISE = "#40E0D0"; // support (put walls, below price)
const CRIMSON = "#E0183C"; // resistance (call walls, above price)
const BONE = "#E8E2D0"; // bone-white: candle borders + up body
const COAL = "#0A0A0A"; // near-black: down body (reads against the lit field)

/**
 * SVG/DOM overlay on top of the heatmap canvas: Call/Put walls + Gamma Flip
 * (key levels, PRD #4) and the forward PRICE TRACE over time. Strikes map to Y
 * by the field's strike range; the price trace maps each replay minute to X.
 * Wall count honors the toolbar Top 1/2/3 picker.
 */
export function HeatmapOverlay({ priceGrid, className }: HeatmapOverlayProps) {
  const levels = useDashboardStore((s) => s.snapshot.levels);
  const wallCount = useDashboardStore((s) => s.wallCount);
  const mode = useDashboardStore((s) => s.mode);
  const frames = useDashboardStore((s) => s.frames);
  const frameIndex = useDashboardStore((s) => s.frameIndex);
  const candleSize = useDashboardStore((s) => s.candleSize);

  const lo = priceGrid[0] ?? 0;
  const hi = priceGrid[priceGrid.length - 1] ?? lo + 1;
  const span = hi - lo || 1;

  // strike -> vertical % (0 = top = highest strike). Clamped, so EOD-fixed walls
  // outside the current zoom window pin to the top/bottom edge instead of vanishing.
  const yPct = (strike: number) => {
    const t = (strike - lo) / span;
    return Math.max(0, Math.min(100, (1 - t) * 100));
  };

  const callWalls = levels.call_walls.slice(0, wallCount);
  const putWalls = levels.put_walls.slice(0, wallCount);

  // Forward price trace across the visible replay minutes.
  const tracePath = useMemo(() => {
    if (mode !== "REPLAY" || frames.length === 0) return "";
    const last = Math.min(frameIndex, frames.length - 1);
    if (last <= 0) return "";
    const pts: string[] = [];
    for (let i = 0; i <= last; i++) {
      const f = frames[i];
      if (!f) continue;
      const x = (i / last) * 100;
      const y = yPct(f.forward);
      pts.push(`${x.toFixed(3)},${y.toFixed(3)}`);
    }
    return pts.length > 1 ? "M " + pts.join(" L ") : "";
  }, [mode, frames, frameIndex, lo, hi]); // eslint-disable-line react-hooks/exhaustive-deps

  // OHLC candles share buildReplayField2D's sliding window (candleWindow), so
  // each candle sits exactly over its heatmap column: CONSTANT width, left
  // aligned, the right 25% always empty, oldest dropping as the newest enters.
  // Falls back to the price line when frames carry no ohlc (old sessions / mock).
  const candles = useMemo(() => {
    if (mode !== "REPLAY" || frames.length === 0) return [];
    const { bins, totalCols } = candleWindow(frames.length, frameIndex, candleSize);
    if (bins.length === 0) return [];
    const halfW = (100 / totalCols) * 0.35;
    const out: {
      xCenter: number; halfW: number; oY: number; hY: number; lY: number; cY: number; up: boolean;
    }[] = [];
    bins.forEach(([start, end], k) => {
      let o: number | null = null;
      let c = 0;
      let h = -Infinity;
      let l = Infinity;
      let any = false;
      for (let i = start; i <= end; i++) {
        const oh = frames[i]?.ohlc;
        if (!oh) continue;
        if (o === null) o = oh.o;
        c = oh.c;
        if (oh.h > h) h = oh.h;
        if (oh.l < l) l = oh.l;
        any = true;
      }
      if (!any || o === null) return;
      out.push({
        xCenter: ((k + 0.5) / totalCols) * 100,
        halfW,
        oY: yPct(o),
        hY: yPct(h),
        lY: yPct(l),
        cY: yPct(c),
        up: c >= o,
      });
    });
    return out;
  }, [mode, frames, frameIndex, candleSize, lo, hi]); // eslint-disable-line react-hooks/exhaustive-deps

  // Per-candle level dots: at each candle's X, mark where the major LONG GEX
  // (turquoise), major SHORT GEX (crimson), and zero-gamma flip (bone) sat that
  // minute — derived from the frame's own profile/levels. They form a moving
  // trail over time, NOT a single vertical line: as the major level migrates
  // strike-to-strike the dot follows it candle by candle.
  const levelDots = useMemo(() => {
    if (mode !== "REPLAY" || frames.length === 0) return [];
    const { bins, totalCols } = candleWindow(frames.length, frameIndex, candleSize);
    const out: { x: number; y: number; color: string; key: string }[] = [];
    bins.forEach(([, end], k) => {
      const f = frames[end];
      if (!f) return;
      const x = ((k + 0.5) / totalCols) * 100;
      let maxV = -Infinity;
      let minV = Infinity;
      let maxS: number | null = null;
      let minS: number | null = null;
      for (const r of f.profile) {
        if (r.net_gex > maxV) { maxV = r.net_gex; maxS = r.strike; }
        if (r.net_gex < minV) { minV = r.net_gex; minS = r.strike; }
      }
      if (maxS !== null && maxV > 0 && maxS >= lo && maxS <= hi)
        out.push({ x, y: yPct(maxS), color: TURQUOISE, key: `lg${k}` });
      if (minS !== null && minV < 0 && minS >= lo && minS <= hi)
        out.push({ x, y: yPct(minS), color: CRIMSON, key: `sh${k}` });
      const flip = f.levels.gamma_flip;
      if (flip !== null && flip >= lo && flip <= hi)
        out.push({ x, y: yPct(flip), color: BONE, key: `zg${k}` });
    });
    return out;
  }, [mode, frames, frameIndex, candleSize, lo, hi]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className={`pointer-events-none absolute inset-0 ${className ?? ""}`}>
      {/* Price candles (OHLC over time) when available, else the forward line.
          preserveAspectRatio=none + non-scaling wick stroke keeps wicks crisp. */}
      {candles.length > 0 ? (
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden
        >
          {candles.map((c, i) => {
            const bodyTop = Math.min(c.oY, c.cY);
            const bodyH = Math.max(0.4, Math.abs(c.cY - c.oY));
            return (
              <g key={i}>
                <line
                  x1={c.xCenter}
                  y1={c.hY}
                  x2={c.xCenter}
                  y2={c.lY}
                  stroke={BONE}
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                />
                <rect
                  x={c.xCenter - c.halfW}
                  y={bodyTop}
                  width={c.halfW * 2}
                  height={bodyH}
                  fill={c.up ? BONE : COAL}
                  stroke={BONE}
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                />
              </g>
            );
          })}
        </svg>
      ) : (
        tracePath && (
          <svg
            className="absolute inset-0 h-full w-full"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            aria-hidden
          >
            <path
              d={tracePath}
              fill="none"
              stroke="var(--color-text-primary)"
              strokeOpacity={0.85}
              strokeWidth={1.25}
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        )
      )}

      {/* Per-candle level dots (major long/short GEX + zero gamma), one per
          candle X, forming a moving trail. Rendered as DOM dots (not in the
          aspect-stretched SVG) so they stay round. */}
      {levelDots.map((d) => (
        <div
          key={d.key}
          className="absolute h-[4px] w-[4px] -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{ left: `${d.x}%`, top: `${d.y}%`, backgroundColor: d.color }}
        />
      ))}

      {/* Call/Put walls by OI are EOD-fixed: always drawn all day, never
          hidden. If price moves past a wall, yPct clamps it to the top/bottom
          edge instead of dropping it. FLIP line and the forward price line are
          gone — zero gamma is now a per-candle dot, and the current price is
          shown only by the white tag in the shared axis panel. */}
      {callWalls.map((s, i) => (
        <LevelLine key={`c${s}`} y={yPct(s)} color={CRIMSON} label={`C${i + 1}`} value={s} />
      ))}

      {putWalls.map((s, i) => (
        <LevelLine key={`p${s}`} y={yPct(s)} color={TURQUOISE} label={`P${i + 1}`} value={s} />
      ))}
    </div>
  );
}

function LevelLine({
  y,
  color,
  label,
  value,
  dashed = false,
  priceTag = false,
}: {
  y: number;
  color: string;
  label: string;
  value: number;
  dashed?: boolean;
  priceTag?: boolean;
}) {
  return (
    <div className="absolute left-0 right-0" style={{ top: `${y}%` }}>
      <div
        className="absolute left-0 right-0 -translate-y-1/2"
        style={{
          top: 0,
          borderTop: `1px ${dashed ? "dashed" : "solid"} ${color}`,
          opacity: dashed ? 0.7 : 0.85,
        }}
      />
      <div
        className="absolute right-4 -translate-y-1/2 rounded-sm border bg-surface px-4 py-px font-mono text-[9px] tabular-nums"
        style={{ top: 0, borderColor: color, color }}
      >
        {label && <span className="mr-2">{label}</span>}
        <NumberReadout value={value} decimals={priceTag ? 2 : 0} size="sm" className="text-[9px]" />
      </div>
    </div>
  );
}
