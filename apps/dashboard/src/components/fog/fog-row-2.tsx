"use client";

/**
 * FogRow2 — interactive zone of FOG page (gamma profile + price chart).
 * Client component karena LevelsDropdown perlu useState untuk toggle, dan
 * HeatmapField perlu canvas refs (browser-only).
 *
 * Composition (right column):
 *   <div relative>
 *     <HeatmapField />     ← Canvas2D: GEX field + bloom + contour, z-0
 *     <PriceChart transparent />  ← SVG: candles + lines + levels, z-10
 *   </div>
 */

import { useState, useLayoutEffect, useRef } from "react";
import { GammaProfile } from "@/components/fog/gamma-profile";
import { PriceChart, type Candle } from "@/components/fog/price-chart";
import { HeatmapField } from "@/components/fog/heatmap-field";
import {
  LevelsDropdown,
  DEFAULT_LEVELS,
  type LevelsState,
} from "@/components/fog/levels-dropdown";
import type { GexField } from "@/lib/dummy-field";

type Wall = { strike: number; gammaDollar: number };
type Strike = { strike: number; gamma: number };

type Props = {
  gammaProfile: Strike[];
  candles: Candle[];
  secondary: Array<{ t: number; v: number }>;
  callWalls: Wall[];
  putWalls: Wall[];
  spot: number;
  flip: number;
  instrument: string;
  field: GexField;
  sessionHigh: number;
  sessionLow: number;
};

const CHART_HEIGHT = 520;

export function FogRow2({
  gammaProfile,
  candles,
  secondary,
  callWalls,
  putWalls,
  spot,
  flip,
  instrument,
  field,
  sessionHigh,
  sessionLow,
}: Props) {
  const [levels, setLevels] = useState<LevelsState>(DEFAULT_LEVELS);

  // Measure right-column chart container for canvas resize
  const stageRef = useRef<HTMLDivElement>(null);
  const [stageW, setStageW] = useState(0);

  useLayoutEffect(() => {
    if (!stageRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) setStageW(Math.round(e.contentRect.width));
    });
    ro.observe(stageRef.current);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="grid grid-cols-12 gap-3 mb-3">
      {/* LEFT — GEX profile vertical (25%) */}
      <div className="col-span-3 border border-[color:var(--hairline)] p-4">
        <div className="flex items-baseline justify-between mb-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3">
            γ Profile
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3">
            per strike
          </span>
        </div>
        <GammaProfile
          data={gammaProfile}
          spot={spot}
          callWalls={callWalls}
          putWalls={putWalls}
          sessionHigh={sessionHigh}
          sessionLow={sessionLow}
        />
      </div>

      {/* RIGHT — candlestick chart (75%) */}
      <div className="col-span-9 border border-[color:var(--hairline)] p-4">
        <div className="flex items-baseline justify-between mb-2 gap-3">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3 shrink-0">
            Price · /{instrument} · last 2h · 1m
          </span>
          <LevelsDropdown value={levels} onChange={setLevels} />
        </div>

        {/* Stage: heatmap + svg chart layered */}
        <div
          ref={stageRef}
          className="relative w-full"
          style={{ height: CHART_HEIGHT }}
        >
          {/* z-0: heatmap canvas (rendered only after we have a width) */}
          {stageW > 0 && (
            <div className="absolute inset-0">
              <HeatmapField
                field={field}
                width={stageW}
                height={CHART_HEIGHT}
                bloomIntensity={1.0}
                contourCount={9}
              />
            </div>
          )}

          {/* z-10: candles + lines + levels SVG, transparent */}
          <div className="absolute inset-0">
            <PriceChart
              candles={candles}
              secondary={secondary}
              callWalls={callWalls}
              putWalls={putWalls}
              spot={spot}
              flip={flip}
              levels={levels}
              height={CHART_HEIGHT}
              transparent
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default FogRow2;
