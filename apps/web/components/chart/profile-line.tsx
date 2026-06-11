"use client";

import { useMemo } from "react";
import type { ProfileRow } from "@flowdesk/contracts";
import type { YScale } from "../../lib/scale";
import { useDashboardStore } from "../../lib/store";

export interface ProfileLineProps {
  profile: ProfileRow[];
  /** Which signed series to draw. */
  metric: "GEX" | "DEX";
  /** Shared vertical scale (strike -> y), owned by the chart layout. */
  scale: YScale;
  /** Pixel width of the profile panel. */
  width: number;
  className?: string;
}

const TURQUOISE = "#40E0D0";
const CRIMSON = "#E0183C";
const BONE = "#E8E2D0"; // start-of-day gamma marker

/**
 * Left profile panel: horizontal BARS per strike across a centered zero
 * baseline. Positive extends right (turquoise), negative extends left
 * (crimson); bar length is proportional to |value|. Rows use the shared
 * Y-scale so each bar aligns with its heatmap row sign-for-sign.
 */
export function ProfileLine({
  profile,
  metric,
  scale,
  width,
  className,
}: ProfileLineProps) {
  const mode = useDashboardStore((s) => s.mode);
  const frames = useDashboardStore((s) => s.frames);
  const frameIndex = useDashboardStore((s) => s.frameIndex);

  const { bars, zeroX } = useMemo(() => {
    const values = profile.map((r) => (metric === "GEX" ? r.net_gex : r.net_dex));
    const maxAbs = values.reduce((m, v) => Math.max(m, Math.abs(v)), 0) || 1;
    // Zero baseline centered; leave an 8px gutter each side.
    const usable = Math.max(1, width - 16);
    const zero = 8 + usable / 2;
    const half = usable / 2;

    // Row spacing in px between adjacent strikes -> bar thickness (~70%, min 1).
    const span = scale.strikeMax - scale.strikeMin || 1;
    const rowPx = (scale.height * scale.step) / span;
    const thickness = Math.max(1, rowPx * 0.7);

    const out = profile.map((r, i) => {
      const v = values[i] ?? 0;
      const len = (Math.abs(v) / maxAbs) * half;
      const y = scale.yOf(r.strike);
      const positive = v >= 0;
      return {
        x: positive ? zero : zero - len,
        y: y - thickness / 2,
        len,
        thickness,
        color: positive ? TURQUOISE : CRIMSON,
        key: r.strike,
      };
    });
    return { bars: out, zeroX: zero };
  }, [profile, metric, scale, width]);

  // Start-of-day gamma marker (white dot) + the trail of strikes the major GEX
  // level has visited this session (faint gray horizontal lines = "gamma was
  // here"). Major GEX = argmax net_gex within each frame's profile.
  const { startY, trailYs } = useMemo(() => {
    if (mode !== "REPLAY" || frames.length === 0)
      return { startY: null as number | null, trailYs: [] as number[] };
    const majorStrike = (f: { profile: ProfileRow[] }): number | null => {
      let maxV = -Infinity;
      let s: number | null = null;
      for (const r of f.profile) {
        if (r.net_gex > maxV) { maxV = r.net_gex; s = r.strike; }
      }
      return maxV > 0 ? s : null;
    };
    const first = frames[0];
    const sod = first ? majorStrike(first) : null;
    const last = Math.min(frameIndex, frames.length - 1);
    const seen = new Set<number>();
    for (let i = 0; i <= last; i++) {
      const f = frames[i];
      if (!f) continue;
      const s = majorStrike(f);
      if (s !== null) seen.add(s);
    }
    return {
      startY: sod !== null ? scale.yOf(sod) : null,
      trailYs: [...seen].map((s) => scale.yOf(s)),
    };
  }, [mode, frames, frameIndex, scale]);

  return (
    <svg
      width={width}
      height={scale.height}
      viewBox={`0 0 ${width} ${scale.height}`}
      className={className}
      role="img"
      aria-label={`Net ${metric} bars by strike`}
      preserveAspectRatio="none"
    >
      {/* zero baseline */}
      <line
        x1={zeroX}
        y1={0}
        x2={zeroX}
        y2={scale.height}
        stroke="var(--color-border)"
        strokeWidth={1}
        strokeDasharray="2 4"
      />
      {/* Gamma trail: faint gray horizontal lines at every strike the major GEX
          has visited this session ("gamma was here"). Drawn behind the bars. */}
      {trailYs.map((y, i) => (
        <line
          key={`trail${i}`}
          x1={0}
          y1={y}
          x2={width}
          y2={y}
          stroke="#9CA3AF"
          strokeOpacity={0.22}
          strokeWidth={1}
        />
      ))}
      {bars.map((b) => (
        <rect
          key={b.key}
          x={b.x}
          y={b.y}
          width={Math.max(0, b.len)}
          height={b.thickness}
          fill={b.color}
        />
      ))}
      {/* Start-of-day gamma marker (white dot at the session-open major GEX). */}
      {startY !== null && (
        <circle cx={zeroX} cy={startY} r={3} fill={BONE} stroke="#000" strokeWidth={0.5} />
      )}
    </svg>
  );
}
