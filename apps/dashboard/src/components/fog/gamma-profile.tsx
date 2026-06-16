"use client";

/**
 * GammaProfile — TRACE-style VERTICAL diverging horizontal-bar chart.
 *
 * Layout:
 *   - Y-axis: strikes (top = highest strike, descending), kelipatan 5 ditampilkan semua
 *   - X-axis: gamma-dollar magnitude, signed
 *   - Spine: vertical baseline at x = 0
 *   - Bars LEFT  = put-side γ (brick)
 *   - Bars RIGHT = call-side γ (bone)
 *
 * Color mapping (label warna):
 *   - Top-1 wall (largest |γ$|): RED (brick-glow)
 *   - Top-2, Top-3 walls:        WHITE (bone-1)
 *   - Spot (nearest strike):     ORANGE (#FB923C)
 *   - All others:                DIM GRAY (bone-3, low alpha)
 *
 * Spot tidak lagi pakai dashed line — diwakili oleh warna label-nya saja.
 */

type Strike = { strike: number; gamma: number };
type Props = {
  data: Strike[];
  spot: number;
  callWalls: { strike: number }[];
  putWalls: { strike: number }[];
  height?: number;
};

const COLOR = {
  spot: "#FB923C", // orange-400
  topWall: "#D54452", // brick-glow
  midWall: "#FAFAF7", // bone-0
  dim: "rgba(250,250,247,0.32)", // bone faded — strike biasa
} as const;

export function GammaProfile({
  data,
  spot,
  callWalls,
  putWalls,
  height = 520,
}: Props) {
  if (data.length === 0) return null;

  // Sort descending — top of chart = highest strike (TRACE convention)
  const sorted = [...data].sort((a, b) => b.strike - a.strike);

  // ─── Color resolution per strike ──────────────────────────────
  // Find nearest strike to spot
  const nearestSpotStrike = sorted.reduce((acc, d) =>
    Math.abs(d.strike - spot) < Math.abs(acc.strike - spot) ? d : acc
  ).strike;

  // Top-1 wall = largest |γ$| across BOTH sides; top-2 & top-3 = walls list
  const allWalls = [...callWalls, ...putWalls]
    .map((w) => ({
      strike: w.strike,
      mag: Math.abs(sorted.find((s) => s.strike === w.strike)?.gamma ?? 0),
    }))
    .sort((a, b) => b.mag - a.mag);
  const topWallStrike = allWalls[0]?.strike;
  const midWallStrikes = new Set(allWalls.slice(1, 3).map((w) => w.strike));

  const colorFor = (strike: number) => {
    if (strike === nearestSpotStrike) return COLOR.spot;
    if (strike === topWallStrike) return COLOR.topWall;
    if (midWallStrikes.has(strike)) return COLOR.midWall;
    return COLOR.dim;
  };

  const weightFor = (strike: number) => {
    if (strike === nearestSpotStrike) return 600;
    if (strike === topWallStrike) return 600;
    if (midWallStrikes.has(strike)) return 500;
    return 400;
  };

  // ─── SVG geometry ─────────────────────────────────────────────
  const W = 360;
  const H = height;
  const PAD_LEFT = 50;
  const PAD_RIGHT = 8;
  const PAD_Y = 14;

  const minStrike = Math.min(...sorted.map((d) => d.strike));
  const maxStrike = Math.max(...sorted.map((d) => d.strike));
  const maxAbsGamma = Math.max(...sorted.map((d) => Math.abs(d.gamma)), 1);

  const yOf = (s: number) => {
    const t = (maxStrike - s) / (maxStrike - minStrike || 1);
    return PAD_Y + t * (H - 2 * PAD_Y);
  };

  const spineX = PAD_LEFT + (W - PAD_LEFT - PAD_RIGHT) / 2;
  const halfW = (W - PAD_LEFT - PAD_RIGHT) / 2;
  const xOf = (g: number) => spineX + (g / maxAbsGamma) * halfW;

  const rowH = (H - 2 * PAD_Y) / sorted.length;
  const barH = Math.max(rowH * 0.7, 1.5);

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto"
        preserveAspectRatio="none"
        aria-label="Gamma profile per strike (vertical)"
      >
        {/* Spine */}
        <line
          x1={spineX}
          x2={spineX}
          y1={PAD_Y}
          y2={H - PAD_Y}
          stroke="rgba(250,250,247,0.18)"
          strokeWidth={1}
        />

        {/* Header axis labels */}
        <text
          x={PAD_LEFT + 2}
          y={PAD_Y - 3}
          fontFamily="ui-monospace, monospace"
          fontSize={8.5}
          fill="rgba(250,250,247,0.4)"
          letterSpacing="0.18em"
        >
          PUTS ←
        </text>
        <text
          x={W - PAD_RIGHT - 2}
          y={PAD_Y - 3}
          textAnchor="end"
          fontFamily="ui-monospace, monospace"
          fontSize={8.5}
          fill="rgba(250,250,247,0.4)"
          letterSpacing="0.18em"
        >
          → CALLS
        </text>

        {/* Bars + strike labels — every strike shown (kelipatan 5) */}
        {sorted.map((d) => {
          const y = yOf(d.strike) - barH / 2;
          const x = d.gamma >= 0 ? spineX : xOf(d.gamma);
          const w = Math.abs(xOf(d.gamma) - spineX);
          const fill =
            d.gamma >= 0 ? "rgba(250,250,247,0.55)" : "rgba(213,68,82,0.7)";
          const labelColor = colorFor(d.strike);
          const labelWeight = weightFor(d.strike);

          return (
            <g key={d.strike}>
              <rect
                x={x}
                y={y}
                width={Math.max(w, 0.5)}
                height={barH}
                fill={fill}
              />
              <text
                x={PAD_LEFT - 6}
                y={yOf(d.strike) + 3}
                textAnchor="end"
                fontFamily="ui-monospace, monospace"
                fontSize={9}
                fontWeight={labelWeight}
                fill={labelColor}
                className="tabular-nums"
              >
                {d.strike.toFixed(0)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export default GammaProfile;
