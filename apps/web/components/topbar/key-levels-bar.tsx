"use client";

import { useDashboardStore } from "../../lib/store";
import { NumberReadout } from "../ui/number-readout";

export interface KeyLevelsBarProps {
  className?: string;
}

const TURQUOISE = "#40E0D0"; // support (put walls, below price)
const CRIMSON = "#E0183C"; // resistance (call walls, above price)

/**
 * Thin key-levels strip under the topbar: the active snapshot's Call/Put walls
 * (OI, static), Gamma Flip + Largest GEX/DEX (VOL, dynamic). Resistance levels
 * (call walls) read crimson, support (put walls) turquoise, neutral levels
 * muted. Honors the toolbar Top 1/2/3 wall picker. Numbers in JetBrains Mono.
 */
export function KeyLevelsBar({ className }: KeyLevelsBarProps) {
  const levels = useDashboardStore((s) => s.snapshot.levels);
  const wallCount = useDashboardStore((s) => s.wallCount);

  const callWalls = levels.call_walls.slice(0, wallCount);
  const putWalls = levels.put_walls.slice(0, wallCount);

  return (
    <div
      className={`flex h-[28px] shrink-0 items-center gap-12 overflow-x-auto border-b border-border bg-surface px-12 ${className ?? ""}`}
      role="navigation"
      aria-label="Key levels"
    >
      <span className="font-display text-[10px] uppercase tracking-[0.08em] text-muted">
        Key Levels
      </span>

      {callWalls.map((s, i) => (
        <LevelChip key={`c${s}`} label={`Call Wall${wallCount > 1 ? ` ${i + 1}` : ""}`} value={s} color={CRIMSON} />
      ))}
      {putWalls.map((s, i) => (
        <LevelChip key={`p${s}`} label={`Put Wall${wallCount > 1 ? ` ${i + 1}` : ""}`} value={s} color={TURQUOISE} />
      ))}
      {levels.gamma_flip !== null && (
        <LevelChip label="Gamma Flip" value={levels.gamma_flip} color="var(--color-text-muted)" decimals={2} />
      )}
      {levels.largest_gex !== null && (
        <LevelChip label="Largest GEX" value={levels.largest_gex} color="var(--color-text-primary)" />
      )}
      {levels.largest_dex !== null && (
        <LevelChip label="Largest DEX" value={levels.largest_dex} color="var(--color-text-primary)" />
      )}
    </div>
  );
}

function LevelChip({
  label,
  value,
  color,
  decimals = 0,
}: {
  label: string;
  value: number;
  color: string;
  decimals?: number;
}) {
  return (
    <span className="flex shrink-0 items-center gap-4">
      <span
        className="inline-block h-8 w-8 rounded-full"
        style={{ backgroundColor: color }}
        aria-hidden
      />
      <span className="font-display text-[10px] uppercase tracking-[0.04em] text-muted">
        {label}
      </span>
      <NumberReadout value={value} decimals={decimals} size="sm" className="text-[11px] text-fg" />
    </span>
  );
}
