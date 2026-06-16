"use client";

/**
 * FogRow2 — interactive zone of FOG page (gamma profile + price chart).
 * Client component karena LevelsDropdown perlu useState untuk toggle.
 *
 * Menerima data dari parent (server component) sebagai props.
 */

import { useState } from "react";
import { GammaProfile } from "@/components/fog/gamma-profile";
import { PriceChart, type Candle } from "@/components/fog/price-chart";
import {
  LevelsDropdown,
  DEFAULT_LEVELS,
  type LevelsState,
} from "@/components/fog/levels-dropdown";

type Wall = { strike: number; gammaDollar: number };
type Strike = { strike: number; gamma: number };

type Props = {
  gammaProfile: Strike[];
  candles: Candle[];
  callWalls: Wall[];
  putWalls: Wall[];
  spot: number;
  flip: number;
  instrument: string;
};

export function FogRow2({
  gammaProfile,
  candles,
  callWalls,
  putWalls,
  spot,
  flip,
  instrument,
}: Props) {
  const [levels, setLevels] = useState<LevelsState>(DEFAULT_LEVELS);

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
        <PriceChart
          candles={candles}
          callWalls={callWalls}
          putWalls={putWalls}
          spot={spot}
          flip={flip}
          levels={levels}
        />
      </div>
    </div>
  );
}

export default FogRow2;
