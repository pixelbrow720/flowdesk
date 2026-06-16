"use client";

/**
 * PriceChart — TRACE-style price action panel with horizontal level overlays.
 *
 * Renders a simple line/area chart of intraday price + horizontal lines
 * for: top-3 call walls, top-3 put walls, spot, gamma-flip level.
 *
 * NOTE: Currently fed by synthetic/dummy bars. Replace `data` with real
 * intraday OHLC series from /api/bars/{instrument} once feed wiring lands.
 */

type Bar = { t: number; price: number };
type Level = { y: number; label: string; tone: "call" | "put" | "spot" | "flip" };

type Props = {
  bars: Bar[];
  callWalls: { strike: number }[];
  putWalls: { strike: number }[];
  spot: number;
  flip: number;
  height?: number;
};

const TONE = {
  call: { stroke: "rgba(250,250,247,0.55)", text: "rgba(250,250,247,0.85)" },
  put: { stroke: "rgba(213,68,82,0.7)", text: "#D54452" },
  spot: { stroke: "#40E0D0", text: "#40E0D0" }, // turquoise = active spot
  flip: { stroke: "rgba(184,51,62,0.55)", text: "#D54452" },
} as const;

export function PriceChart({
  bars,
  callWalls,
  putWalls,
  spot,
  flip,
  height = 520,
}: Props) {
  if (bars.length === 0) return null;

  const W = 900;
  const H = height;
  const PAD_L = 14;
  const PAD_R = 88; // room for level labels on right
  const PAD_Y = 18;

  // Determine y range: cover bars + all levels with breathing room
  const allYs = [
    ...bars.map((b) => b.price),
    ...callWalls.map((w) => w.strike),
    ...putWalls.map((w) => w.strike),
    spot,
    flip,
  ];
  const yMin = Math.min(...allYs);
  const yMax = Math.max(...allYs);
  const yRange = yMax - yMin || 1;
  const yPad = yRange * 0.05;
  const yLo = yMin - yPad;
  const yHi = yMax + yPad;

  const xMin = bars[0].t;
  const xMax = bars[bars.length - 1].t;

  const xOf = (t: number) =>
    PAD_L + ((t - xMin) / (xMax - xMin || 1)) * (W - PAD_L - PAD_R);
  const yOf = (p: number) =>
    PAD_Y + ((yHi - p) / (yHi - yLo)) * (H - 2 * PAD_Y);

  // Build line path
  const linePath = bars
    .map((b, i) => `${i === 0 ? "M" : "L"} ${xOf(b.t).toFixed(2)} ${yOf(b.price).toFixed(2)}`)
    .join(" ");

  // Area path (line + close to baseline at bottom)
  const areaPath =
    linePath +
    ` L ${xOf(bars[bars.length - 1].t).toFixed(2)} ${(H - PAD_Y).toFixed(2)}` +
    ` L ${xOf(bars[0].t).toFixed(2)} ${(H - PAD_Y).toFixed(2)} Z`;

  const levels: Level[] = [
    ...callWalls.map((w, i) => ({
      y: w.strike,
      label: `CW${i + 1} ${w.strike.toFixed(0)}`,
      tone: "call" as const,
    })),
    ...putWalls.map((w, i) => ({
      y: w.strike,
      label: `PW${i + 1} ${w.strike.toFixed(0)}`,
      tone: "put" as const,
    })),
    { y: flip, label: `FLIP ${flip.toFixed(2)}`, tone: "flip" },
    { y: spot, label: `SPOT ${spot.toFixed(2)}`, tone: "spot" },
  ];

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto"
        preserveAspectRatio="none"
        aria-label="Price chart with key levels"
      >
        {/* Subtle grid: 4 horizontal gridlines */}
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

        {/* Level lines (rendered before price so price sits on top) */}
        {levels.map((lv, i) => {
          const y = yOf(lv.y);
          const tone = TONE[lv.tone];
          const dash =
            lv.tone === "spot" ? "0" : lv.tone === "flip" ? "6 4" : "3 3";
          return (
            <g key={`${lv.tone}-${i}`}>
              <line
                x1={PAD_L}
                x2={W - PAD_R}
                y1={y}
                y2={y}
                stroke={tone.stroke}
                strokeWidth={lv.tone === "spot" ? 1.25 : 1}
                strokeDasharray={dash}
              />
              <text
                x={W - PAD_R + 4}
                y={y + 3}
                fontFamily="ui-monospace, monospace"
                fontSize={9.5}
                fill={tone.text}
                letterSpacing="0.08em"
                className="tabular-nums"
              >
                {lv.label}
              </text>
            </g>
          );
        })}

        {/* Price area */}
        <path d={areaPath} fill="url(#priceAreaFill)" />
        <defs>
          <linearGradient id="priceAreaFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(64,224,208,0.18)" />
            <stop offset="100%" stopColor="rgba(64,224,208,0)" />
          </linearGradient>
        </defs>
        {/* Price line */}
        <path
          d={linePath}
          fill="none"
          stroke="#40E0D0"
          strokeWidth={1.4}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}

export default PriceChart;
