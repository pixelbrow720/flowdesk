"use client";

/**
 * GammaProfile — signed gamma-dollar per strike, vertical bars on a baseline.
 *
 * Convention:
 *   - Bars above baseline = positive (call-side gamma)
 *   - Bars below baseline = negative (put-side gamma)
 *   - Spot marker = vertical brick line
 *
 * Pure SVG, no chart lib — matches landing's stdlib-render aesthetic.
 */

type Strike = { strike: number; gamma: number };
type Props = {
  data: Strike[];
  spot: number;
  height?: number;
};

export function GammaProfile({ data, spot, height = 220 }: Props) {
  if (data.length === 0) return null;

  const W = 1000; // viewBox width — scales responsively
  const H = height;
  const PAD = 16;

  const minStrike = Math.min(...data.map((d) => d.strike));
  const maxStrike = Math.max(...data.map((d) => d.strike));
  const maxAbsGamma = Math.max(...data.map((d) => Math.abs(d.gamma)), 1);

  const xOf = (s: number) =>
    PAD + ((s - minStrike) / (maxStrike - minStrike)) * (W - 2 * PAD);
  const yBaseline = H / 2;
  const halfH = (H - 2 * PAD) / 2;
  const yOf = (g: number) => yBaseline - (g / maxAbsGamma) * halfH;

  const barW = ((W - 2 * PAD) / data.length) * 0.7;

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto"
        preserveAspectRatio="none"
        aria-label="Gamma profile per strike"
      >
        {/* Baseline */}
        <line
          x1={PAD}
          x2={W - PAD}
          y1={yBaseline}
          y2={yBaseline}
          stroke="rgba(250,250,247,0.16)"
          strokeWidth={1}
        />

        {/* Bars */}
        {data.map((d) => {
          const x = xOf(d.strike) - barW / 2;
          const y = d.gamma >= 0 ? yOf(d.gamma) : yBaseline;
          const h = Math.abs(yOf(d.gamma) - yBaseline);
          const fill = d.gamma >= 0 ? "rgba(250,250,247,0.55)" : "rgba(213,68,82,0.7)";
          return (
            <rect
              key={d.strike}
              x={x}
              y={y}
              width={barW}
              height={Math.max(h, 0.5)}
              fill={fill}
            />
          );
        })}

        {/* Spot marker */}
        <line
          x1={xOf(spot)}
          x2={xOf(spot)}
          y1={PAD / 2}
          y2={H - PAD / 2}
          stroke="#D54452"
          strokeWidth={1.25}
          strokeDasharray="3 3"
        />
        <text
          x={xOf(spot) + 6}
          y={PAD + 8}
          fontFamily="ui-monospace, monospace"
          fontSize={10}
          fill="#D54452"
          letterSpacing="0.1em"
        >
          SPOT {spot.toFixed(2)}
        </text>

        {/* X-axis tick labels — only edges + ATM */}
        <text
          x={PAD}
          y={H - 4}
          fontFamily="ui-monospace, monospace"
          fontSize={9}
          fill="rgba(250,250,247,0.45)"
        >
          {minStrike.toFixed(0)}
        </text>
        <text
          x={W - PAD}
          y={H - 4}
          textAnchor="end"
          fontFamily="ui-monospace, monospace"
          fontSize={9}
          fill="rgba(250,250,247,0.45)"
        >
          {maxStrike.toFixed(0)}
        </text>
      </svg>
    </div>
  );
}

export default GammaProfile;
