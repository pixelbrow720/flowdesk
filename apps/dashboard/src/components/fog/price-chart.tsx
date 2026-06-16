"use client";

/**
 * PriceChart — TRACE-style candlestick chart with toggle-able key levels.
 *
 * Renders OHLC candles + horizontal level overlays. Levels persist regardless
 * of where price is (a call wall below spot still renders if user wants —
 * because the EOD-derived dealer book is what it is).
 *
 * Color convention:
 *   - Up candle  (close ≥ open):  turquoise body + wick
 *   - Down candle (close <  open): brick body + wick
 *   - Call wall lines: bone (white-ish) dashed, labeled "CW1/2/3 <strike>"
 *   - Put wall lines:  brick dashed, labeled "PW1/2/3 <strike>"
 *   - Spot line:       orange solid (#FB923C)
 *   - Flip line:       brick long-dashed
 *
 * Toggling levels via parent state (LevelsState).
 */

import type { LevelsState } from "./levels-dropdown";

export type Candle = { t: number; o: number; h: number; l: number; c: number };

type Props = {
  candles: Candle[];
  /** Optional secondary line (e.g. 20-period SMA) to overlay on top of candles. */
  secondary?: Array<{ t: number; v: number }>;
  callWalls: { strike: number }[]; // already top-3 ordered (CW1=biggest)
  putWalls: { strike: number }[];
  spot: number;
  flip: number;
  levels: LevelsState;
  height?: number;
  /** Make the SVG background fully transparent so a heatmap canvas sits below it. */
  transparent?: boolean;
};

const COLOR = {
  up: "#40E0D0", // turquoise
  down: "#D54452", // brick-glow
  call: "rgba(250,250,247,0.65)",
  put: "rgba(213,68,82,0.7)",
  spot: "#FB923C", // orange-400
  flip: "rgba(213,68,82,0.55)",
  callText: "rgba(250,250,247,0.85)",
  putText: "#D54452",
  spotText: "#FB923C",
  flipText: "#D54452",
} as const;

export function PriceChart({
  candles,
  secondary,
  callWalls,
  putWalls,
  spot,
  flip,
  levels,
  height = 520,
  transparent = false,
}: Props) {
  if (candles.length === 0) return null;

  const W = 900;
  const H = height;
  const PAD_L = 14;
  const PAD_R = 88; // room for level labels on right
  const PAD_Y = 18;

  // Slice walls per toggle state — persistent regardless of where price is
  const visibleCallWalls = callWalls.slice(0, levels.callWalls);
  const visiblePutWalls = putWalls.slice(0, levels.putWalls);

  // y-range covers candles + ALL toggled levels (so legend stays in frame
  // even when wall is far from price action)
  const candleYs = candles.flatMap((c) => [c.h, c.l]);
  const levelYs: number[] = [
    ...visibleCallWalls.map((w) => w.strike),
    ...visiblePutWalls.map((w) => w.strike),
    ...(levels.spot ? [spot] : []),
    ...(levels.flip ? [flip] : []),
  ];
  const allYs = [...candleYs, ...levelYs];
  const yMin = Math.min(...allYs);
  const yMax = Math.max(...allYs);
  const yRange = yMax - yMin || 1;
  const yPad = yRange * 0.05;
  const yLo = yMin - yPad;
  const yHi = yMax + yPad;

  const xMin = candles[0].t;
  const xMax = candles[candles.length - 1].t;

  const xOf = (t: number) =>
    PAD_L + ((t - xMin) / (xMax - xMin || 1)) * (W - PAD_L - PAD_R);
  const yOf = (p: number) =>
    PAD_Y + ((yHi - p) / (yHi - yLo)) * (H - 2 * PAD_Y);

  // Candle width: total chart width / count, with gap
  const slotW = (W - PAD_L - PAD_R) / candles.length;
  const bodyW = Math.max(slotW * 0.7, 1.2);

  type Lvl = { y: number; label: string; tone: "call" | "put" | "spot" | "flip" };
  const renderLevels: Lvl[] = [
    ...visibleCallWalls.map((w, i) => ({
      y: w.strike,
      label: `CW${i + 1} ${w.strike.toFixed(0)}`,
      tone: "call" as const,
    })),
    ...visiblePutWalls.map((w, i) => ({
      y: w.strike,
      label: `PW${i + 1} ${w.strike.toFixed(0)}`,
      tone: "put" as const,
    })),
    ...(levels.flip
      ? [{ y: flip, label: `FLIP ${flip.toFixed(2)}`, tone: "flip" as const }]
      : []),
    ...(levels.spot
      ? [{ y: spot, label: `SPOT ${spot.toFixed(2)}`, tone: "spot" as const }]
      : []),
  ];

  // Build path for secondary line (smoothed reference) if provided
  const secondaryPath = secondary && secondary.length
    ? secondary
        .map((p, i) => `${i === 0 ? "M" : "L"} ${xOf(p.t).toFixed(2)} ${yOf(p.v).toFixed(2)}`)
        .join(" ")
    : null;

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto"
        preserveAspectRatio="none"
        aria-label="Price candlestick chart with key levels"
        style={transparent ? { background: "transparent" } : undefined}
      >
        {/* Subtle grid */}
        {[0.25, 0.5, 0.75].map((f) => (
          <line
            key={f}
            x1={PAD_L}
            x2={W - PAD_R}
            y1={PAD_Y + f * (H - 2 * PAD_Y)}
            y2={PAD_Y + f * (H - 2 * PAD_Y)}
            stroke="rgba(250,250,247,0.04)"
            strokeWidth={1}
          />
        ))}

        {/* Level lines (rendered before candles so candles sit on top) */}
        {renderLevels.map((lv, i) => {
          const y = yOf(lv.y);
          const stroke =
            lv.tone === "call"
              ? COLOR.call
              : lv.tone === "put"
                ? COLOR.put
                : lv.tone === "spot"
                  ? COLOR.spot
                  : COLOR.flip;
          const text =
            lv.tone === "call"
              ? COLOR.callText
              : lv.tone === "put"
                ? COLOR.putText
                : lv.tone === "spot"
                  ? COLOR.spotText
                  : COLOR.flipText;
          const dash =
            lv.tone === "spot" ? "0" : lv.tone === "flip" ? "6 4" : "3 3";
          const sw = lv.tone === "spot" ? 1.4 : 1;
          return (
            <g key={`${lv.tone}-${i}`}>
              <line
                x1={PAD_L}
                x2={W - PAD_R}
                y1={y}
                y2={y}
                stroke={stroke}
                strokeWidth={sw}
                strokeDasharray={dash}
              />
              <text
                x={W - PAD_R + 4}
                y={y + 3}
                fontFamily="ui-monospace, monospace"
                fontSize={9.5}
                fill={text}
                letterSpacing="0.08em"
                className="tabular-nums"
              >
                {lv.label}
              </text>
            </g>
          );
        })}

        {/* Candles */}
        {candles.map((c, i) => {
          const cx = xOf(c.t);
          const up = c.c >= c.o;
          const stroke = up ? COLOR.up : COLOR.down;
          const fill = up ? COLOR.up : COLOR.down;
          const yH = yOf(c.h);
          const yL = yOf(c.l);
          const yO = yOf(c.o);
          const yC = yOf(c.c);
          const top = Math.min(yO, yC);
          const bodyH = Math.max(Math.abs(yC - yO), 0.6);
          return (
            <g key={`c-${i}`}>
              {/* wick */}
              <line
                x1={cx}
                x2={cx}
                y1={yH}
                y2={yL}
                stroke={stroke}
                strokeWidth={0.9}
              />
              {/* body */}
              <rect
                x={cx - bodyW / 2}
                y={top}
                width={bodyW}
                height={bodyH}
                fill={fill}
                opacity={up ? 0.9 : 0.85}
              />
            </g>
          );
        })}

        {/* Secondary line (smoothed/reference) — drawn last so sits above candles */}
        {secondaryPath && (
          <path
            d={secondaryPath}
            fill="none"
            stroke="rgba(220,220,220,0.55)"
            strokeWidth={1.1}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        )}
      </svg>
    </div>
  );
}

export default PriceChart;
