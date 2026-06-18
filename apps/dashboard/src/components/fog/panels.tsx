"use client";

/**
 * Fog three-panel strike terminal — the four strike-aligned columns.
 *
 * All columns share ONE row model: every strike is `FOG_ROW_H` px tall and the
 * panels render the SAME ordered `strikes` array, so rows line up across the
 * gutter / left / center / right without a shared grid element. The whole stack
 * lives in one `fog-scroll` flex container (in page.tsx) so it scrolls as one.
 *
 *   gutter  — strike prices (color = current / major-long / major-short)
 *   left    — GEX structure: bidirectional bars + optional EXPERIMENTAL
 *             IV-smile overlay (dotted curve, static)
 *   center  — dynamics: three continuous lines (current / session-high /
 *             session-low) + a mean reference line + animated flow particles,
 *             for the selected metric (GEX or DEX)
 *   right   — DEX structure: same bidirectional-bar language as the left
 *
 * Bars are center-axis bidirectional (turquoise = positive, crimson = negative)
 * matching the hand-built reference look: thin type, hairline `rule`, no heavy
 * borders.
 */

import { useMemo, useState } from "react";
import {
  type MetricKey,
  type MetricSeries,
  type StrikeDatum,
} from "@/components/fog/strikeMath";

/** Fixed row height (px). Center flow canvas math depends on this exact value. */
export const FOG_ROW_H = 22;

/** One self-normalized smile sample (0 = lowest vol in view, 1 = highest). */
export interface SmilePoint {
  price: number;
  norm: number;
}

/* ------------------------------------------------------------------ */
/* Formatting helpers (shared with tooltips)                           */
/* ------------------------------------------------------------------ */

function fmtNotional(v: number): string {
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(1)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

function fmtDelta(v: number): string {
  return (v >= 0 ? "+" : "") + fmtNotional(v).replace("-", "");
}

const pct = (v: number) => `${(v * 50).toFixed(2)}%`;

/* ------------------------------------------------------------------ */
/* StrikeGutter — leftmost price ladder                                */
/* ------------------------------------------------------------------ */

export function StrikeGutter({
  strikes,
  forward,
  majorLongPrice,
  majorShortPrice,
}: {
  strikes: StrikeDatum[];
  forward: number;
  majorLongPrice: number;
  majorShortPrice: number;
}) {
  const TICK = 5;
  return (
    <div className="grid w-16 shrink-0 content-start" style={{ gridAutoRows: `${FOG_ROW_H}px` }}>
      {strikes.map((s) => {
        const isCurrent = Math.abs(s.price - forward) < TICK / 2;
        const isLong = s.price === majorLongPrice;
        const isShort = s.price === majorShortPrice;
        const cls = isCurrent
          ? "text-amber-current"
          : isLong
            ? "text-turquoise-deep"
            : isShort
              ? "text-crimson-deep"
              : "text-bone-3";
        return (
          <div key={s.price} className="flex items-center justify-end pr-3">
            <span className={`font-mono text-[10.5px] leading-none tabular-nums ${cls}`}>
              {s.price.toLocaleString("en-US")}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Shared bidirectional bar row primitive                              */
/* ------------------------------------------------------------------ */

function ZeroAxis({ top }: { top: boolean }) {
  return (
    <div
      className={`pointer-events-none absolute left-1/2 w-px -translate-x-1/2 bg-rule ${
        top ? "top-0" : "-top-[1px]"
      } bottom-0`}
      aria-hidden="true"
    />
  );
}

/** A single center-axis bar (turquoise +, crimson −) with hover tooltip. */
function BarRow({
  label,
  price,
  series,
  showAxisTop,
}: {
  label: string;
  price: number;
  series: MetricSeries;
  showAxisTop: boolean;
}) {
  const [hover, setHover] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const norm = series.current;
  const positive = norm >= 0;
  const color = positive ? "bg-turquoise-deep" : "bg-crimson-deep";
  const left = positive ? "50%" : `calc(50% + ${pct(norm)})`;
  const width = `${(Math.abs(norm) * 50).toFixed(2)}%`;
  const span = series.absHigh - series.absLow;
  const percentile = span > 0 ? ((series.absCurrent - series.absLow) / span) * 100 : 0;
  // Session range hairline (low↔high) — may cross the zero axis. End-cap
  // whiskers mark the extremes so it reads as a range, not just a line.
  const rangeLeft = `calc(50% + ${pct(series.low)})`;
  const rangeWidth = `${((series.high - series.low) * 50).toFixed(2)}%`;
  return (
    <div
      className="relative flex h-full items-center pr-3"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onMouseMove={(e) => setPos({ x: e.clientX, y: e.clientY })}
    >
      <ZeroAxis top={showAxisTop} />
      {/* Session range hairline + end-cap whiskers. */}
      <div
        className="absolute top-1/2 h-px -translate-y-1/2 bg-bone-3/60"
        style={{ left: rangeLeft, width: rangeWidth }}
        aria-hidden="true"
      />
      <div
        className="absolute top-1/2 h-2 w-px -translate-y-1/2 bg-bone-3/60"
        style={{ left: `calc(50% + ${pct(series.low)})` }}
        aria-hidden="true"
      />
      <div
        className="absolute top-1/2 h-2 w-px -translate-y-1/2 bg-bone-3/60"
        style={{ left: `calc(50% + ${pct(series.high)})` }}
        aria-hidden="true"
      />
      <div
        className={`absolute rounded-[2px] ${color} ${hover ? "ring-1 ring-bone-0/50" : ""}`}
        style={{ left, width, height: "70%", top: "15%" }}
      />
      {hover && (
        <div
          className="pointer-events-none fixed z-[100] w-60 rounded-[5px] border border-rule bg-black/95 px-4 py-3 font-mono shadow-xl backdrop-blur-sm"
          style={{ left: pos.x + 18, top: pos.y - 10 }}
        >
          <div className="flex items-center justify-between text-[12px] tracking-[0.12em] text-bone-3">
            <span>{label}</span>
            <span className="tabular-nums text-bone-0">{price.toLocaleString("en-US")}</span>
          </div>
          <div
            className={`mt-1.5 text-[22px] font-semibold leading-none tabular-nums ${
              series.absCurrent >= 0 ? "text-turquoise-deep" : "text-crimson-deep"
            }`}
          >
            {fmtNotional(series.absCurrent)}
          </div>
          <div className="mt-2 text-[11px] tabular-nums text-bone-3">
            {span > 0 ? `${percentile.toFixed(0)}th pct · ` : ""}
            range {fmtNotional(series.absLow)} → {fmtNotional(series.absHigh)}
          </div>
          <div className="mt-2.5 space-y-1 border-t border-rule pt-2 text-[12px] tabular-nums">
            <TooltipRow label="last 5m" v={series.diff5m} />
            <TooltipRow label="last 30m" v={series.diff30m} />
            <TooltipRow label="last 60m" v={series.diff60m} />
          </div>
        </div>
      )}
    </div>
  );
}

function TooltipRow({ label, v }: { label: string; v: number }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-bone-3">{label}</span>
      <span className={v >= 0 ? "text-turquoise-deep" : "text-crimson-deep"}>{fmtDelta(v)}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* MetricBarPanel — left (GEX) / right (DEX): identical bar language   */
/* ------------------------------------------------------------------ */

export function MetricBarPanel({
  strikes,
  metric,
  label,
  smile,
  showSmile,
  className = "flex-1",
}: {
  strikes: StrikeDatum[];
  metric: MetricKey;
  label: string;
  smile?: SmilePoint[] | null;
  showSmile?: boolean;
  className?: string;
}) {
  // IV-smile dots — one per strike, X = self-normalized vol (inset 10..90%),
  // Y = the strike's row center. CSS-positioned dots (round, never distorted)
  // to match the gexbot dotted-smile look. EXPERIMENTAL surface.
  const smileDots = useMemo(() => {
    if (!smile || smile.length < 2 || strikes.length === 0) return [];
    const byPrice = new Map(smile.map((q) => [q.price, q.norm]));
    return strikes
      .map((s, i) => {
        const n = byPrice.get(s.price);
        if (n == null) return null;
        return {
          price: s.price,
          left: 10 + n * 80,
          top: ((i + 0.5) / strikes.length) * 100,
        };
      })
      .filter((d): d is { price: number; left: number; top: number } => d !== null);
  }, [smile, strikes]);

  return (
    <div className={`relative min-w-0 ${className}`}>
      {/* IV-smile overlay — discrete bone dots, self-normalized vol vs strike. */}
      {showSmile && smileDots.length > 0 && (
        <div className="pointer-events-none absolute inset-0 z-20" aria-hidden="true">
          {smileDots.map((d) => (
            <span
              key={d.price}
              className="absolute h-[3px] w-[3px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-bone-3/80"
              style={{ left: `${d.left}%`, top: `${d.top}%` }}
            />
          ))}
        </div>
      )}
      <div className="grid content-start" style={{ gridAutoRows: `${FOG_ROW_H}px` }}>
        {strikes.map((s, i) => (
          <BarRow
            key={s.price}
            label={label}
            price={s.price}
            series={s[metric]}
            showAxisTop={i === 0}
          />
        ))}
      </div>
    </div>
  );
}
