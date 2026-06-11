"use client";

import { useMemo } from "react";
import { rampToCssGradient, type RampStop } from "../../lib/heatmap/oklab";
import { NumberReadout } from "../ui/number-readout";
import type { Basis } from "../../lib/heatmap/field-2d";

export interface ColorbarProps {
  basis: Basis;
  /** Theme mid anchor: black (dark) or white (light). */
  theme: "dark" | "light";
  /** Max abs magnitude the ramp endpoints represent (for the legend ticks). */
  maxAbs: number;
  className?: string;
}

// Locked ramp anchors (PRD #2). Mid changes with theme; ends are fixed.
const LOW = "#40E0D0"; // turquoise = strongest positive
const HIGH = "#E0183C"; // crimson  = strongest negative

function stopsFor(theme: "dark" | "light"): RampStop[] {
  return [
    { stop: 0, color: LOW },
    { stop: 0.5, color: theme === "light" ? "#FFFFFF" : "#000000" },
    { stop: 1, color: HIGH },
  ];
}

const LABELS: Record<Basis, string> = {
  GAMMA: "GEX $",
  DELTA: "DEX $",
};

/**
 * Vertical colorbar for the heatmap. The gradient is sampled in OKLab (matching
 * the shader), top = strongest positive (turquoise), bottom = strongest
 * negative (crimson), neutral in the middle.
 */
export function Colorbar({ basis, theme, maxAbs, className }: ColorbarProps) {
  const gradient = useMemo(
    () => rampToCssGradient(stopsFor(theme), 32, "to bottom"),
    [theme],
  );

  return (
    <div className={`flex h-full flex-col items-start gap-8 ${className ?? ""}`}>
      <span className="font-display text-caption uppercase tracking-[0.04em] text-muted">
        {LABELS[basis]}
      </span>
      <div className="flex flex-1 items-stretch gap-8">
        <div
          className="w-12 rounded-sm border border-border"
          style={{ backgroundImage: gradient }}
          aria-hidden
        />
        <div className="flex flex-col justify-between py-2">
          <span className="flex items-center gap-4">
            <span className="font-display text-caption text-turquoise">+</span>
            <NumberReadout value={maxAbs} compact size="sm" colorBySign />
          </span>
          <span className="font-display text-caption text-muted">0</span>
          <span className="flex items-center gap-4">
            <span className="font-display text-caption text-crimson">−</span>
            <NumberReadout value={-maxAbs} compact size="sm" colorBySign />
          </span>
        </div>
      </div>
    </div>
  );
}
