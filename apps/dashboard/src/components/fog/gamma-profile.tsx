"use client";

/**
 * GammaProfile — TRACE-style VERTICAL diverging horizontal-bar chart.
 *
 * Layout:
 *   - Y-axis: strikes (top = highest strike, descending)
 *   - X-axis: gamma-dollar magnitude, signed
 *   - Spine: vertical baseline at x = 0
 *   - Bars to the LEFT of spine = put-side gamma (brick)
 *   - Bars to the RIGHT of spine = call-side gamma (bone)
 *   - Spot marker: horizontal dashed line at strike == spot
 *
 * Pure SVG, no chart lib. Scales container width via preserveAspectRatio.
 */

type Strike = { strike: number; gamma: number };
type Props = {
  data: Strike[];
  spot: number;
  height?: number;
};

export function GammaProfile({ data, spot, height = 520 }: Props) {
  if (data.length === 0) return null;

  // Sort descending so top of chart = highest strike (TRACE convention)
  const sorted = [...data].sort((a, b) => b.strike - a.strike);

  const W = 600;
  const H = height;
  const PAD_X = 56; // left padding for strike labels
  const PAD_R = 12; // right padding
  const PAD_Y = 14;

  const minStrike = Math.min(...sorted.map((d) => d.strike));
  const maxStrike = Math.max(...sorted.map((d) => d.strike));
  const maxAbsGamma = Math.max(...sorted.map((d) => Math.abs(d.gamma)), 1);

  // Y mapping (strike → y) — descending
  const yOf = (s: number) => {
    const t = (maxStrike - s) / (maxStrike - minStrike || 1);
    return PAD_Y + t * (H - 2 * PAD_Y);
  };

  // X mapping (gamma → x) — diverging from spine at center
  const spineX = PAD_X + (W - PAD_X - PAD_R) / 2;
  const halfW = (W - PAD_X - PAD_R) / 2;
  const xOf = (g: number) => spineX + (g / maxAbsGamma) * halfW;

  const rowH = (H - 2 * PAD_Y) / sorted.length;
  const barH = Math.max(rowH * 0.7, 2);

  // Show ~6 strike labels evenly spaced
  const labelStep = Math.max(1, Math.floor(sorted.length / 6));

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto"
        preserveAspectRatio="none"
        aria-label="Gamma profile per strike (vertical)"
      >
        {/* Spine (x = 0 baseline) */}
        <line
          x1={spineX}
          x2={spineX}
          y1={PAD_Y}
          y2={H - PAD_Y}
          stroke="rgba(250,250,247,0.18)"
          strokeWidth={1}
        />

        {/* Side labels — top */}
        <text
          x={PAD_X + 4}
          y={PAD_Y - 2}
          fontFamily="ui-monospace, monospace"
          fontSize={9}
          fill="rgba(250,250,247,0.45)"
          letterSpacing="0.18em"
        >
          PUTS ←
        </text>
        <text
          x={W - PAD_R - 4}
          y={PAD_Y - 2}
          textAnchor="end"
          fontFamily="ui-monospace, monospace"
          fontSize={9}
          fill="rgba(250,250,247,0.45)"
          letterSpacing="0.18em"
        >
          → CALLS
        </text>

        {/* Bars + strike labels */}
        {sorted.map((d, i) => {
          const y = yOf(d.strike) - barH / 2;
          const x = d.gamma >= 0 ? spineX : xOf(d.gamma);
          const w = Math.abs(xOf(d.gamma) - spineX);
          const fill =
            d.gamma >= 0 ? "rgba(250,250,247,0.55)" : "rgba(213,68,82,0.7)";

          const showLabel = i % labelStep === 0 || i === sorted.length - 1;

          return (
            <g key={d.strike}>
              <rect
                x={x}
                y={y}
                width={Math.max(w, 0.5)}
                height={barH}
                fill={fill}
              />
              {showLabel && (
                <text
                  x={PAD_X - 6}
                  y={yOf(d.strike) + 3}
                  textAnchor="end"
                  fontFamily="ui-monospace, monospace"
                  fontSize={9}
                  fill="rgba(250,250,247,0.45)"
                  className="tabular-nums"
                >
                  {d.strike.toFixed(0)}
                </text>
              )}
            </g>
          );
        })}

        {/* Spot marker — horizontal dashed line */}
        <line
          x1={PAD_X}
          x2={W - PAD_R}
          y1={yOf(spot)}
          y2={yOf(spot)}
          stroke="#D54452"
          strokeWidth={1.25}
          strokeDasharray="3 3"
        />
        <text
          x={W - PAD_R - 4}
          y={yOf(spot) - 4}
          textAnchor="end"
          fontFamily="ui-monospace, monospace"
          fontSize={9.5}
          fill="#D54452"
          letterSpacing="0.1em"
          className="tabular-nums"
        >
          SPOT {spot.toFixed(2)}
        </text>
      </svg>
    </div>
  );
}

export default GammaProfile;
