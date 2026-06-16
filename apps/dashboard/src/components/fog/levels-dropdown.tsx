"use client";

/**
 * LevelsDropdown — single dropdown trigger di header chart.
 * Click trigger → reveal panel dengan grouped controls.
 *
 * Groups:
 *   - Call walls: off / top-1 / top-2 / top-3 (segmented)
 *   - Put walls:  off / top-1 / top-2 / top-3 (segmented)
 *   - Spot:    on/off (toggle)
 *   - Flip:    on/off (toggle)
 *
 * Click outside to close. Esc closes too.
 */

import { useEffect, useRef, useState } from "react";

export type LevelsState = {
  callWalls: 0 | 1 | 2 | 3;
  putWalls: 0 | 1 | 2 | 3;
  spot: boolean;
  flip: boolean;
};

export const DEFAULT_LEVELS: LevelsState = {
  callWalls: 3,
  putWalls: 3,
  spot: true,
  flip: true,
};

type Props = {
  value: LevelsState;
  onChange: (next: LevelsState) => void;
};

export function LevelsDropdown({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const activeCount =
    value.callWalls + value.putWalls + (value.spot ? 1 : 0) + (value.flip ? 1 : 0);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`font-mono text-[10px] uppercase tracking-[0.18em] px-2 py-1 border transition-colors ${
          open
            ? "border-bone-1 text-bone-0 bg-[rgba(250,250,247,0.05)]"
            : "border-[color:var(--hairline)] text-bone-3 hover:text-bone-1 hover:border-bone-3"
        }`}
        aria-expanded={open}
        aria-haspopup="true"
      >
        Levels · {activeCount}
        <span className="ml-1.5 inline-block">{open ? "▴" : "▾"}</span>
      </button>

      {open && (
        <div
          className="absolute right-0 top-[calc(100%+4px)] z-30 w-60 border border-bone-3 bg-ink-0 p-3 shadow-[0_8px_24px_rgba(0,0,0,0.6)]"
          role="menu"
        >
          {/* Call walls segmented */}
          <SegmentedRow
            label="Call walls"
            value={value.callWalls}
            onChange={(n) => onChange({ ...value, callWalls: n })}
          />
          <Hairline />
          {/* Put walls segmented */}
          <SegmentedRow
            label="Put walls"
            value={value.putWalls}
            onChange={(n) => onChange({ ...value, putWalls: n })}
          />
          <Hairline />
          {/* Spot toggle */}
          <ToggleRow
            label="Spot"
            tone="#FB923C"
            checked={value.spot}
            onChange={(b) => onChange({ ...value, spot: b })}
          />
          {/* Flip toggle */}
          <ToggleRow
            label="Gamma flip"
            tone="#D54452"
            checked={value.flip}
            onChange={(b) => onChange({ ...value, flip: b })}
          />
        </div>
      )}
    </div>
  );
}

function Hairline() {
  return <div className="h-px bg-[color:var(--hairline)] my-2" />;
}

function SegmentedRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: 0 | 1 | 2 | 3;
  onChange: (n: 0 | 1 | 2 | 3) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-bone-3">
        {label}
      </span>
      <div className="flex border border-[color:var(--hairline)]">
        {([0, 1, 2, 3] as const).map((n) => {
          const active = value === n;
          return (
            <button
              key={n}
              type="button"
              onClick={() => onChange(n)}
              className={`font-mono text-[10px] tabular-nums w-7 py-0.5 transition-colors ${
                active
                  ? "bg-[rgba(250,250,247,0.12)] text-bone-0"
                  : "text-bone-3 hover:text-bone-1"
              } ${n > 0 ? "border-l border-[color:var(--hairline)]" : ""}`}
              aria-pressed={active}
              title={n === 0 ? "off" : `top-${n}`}
            >
              {n === 0 ? "·" : n}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ToggleRow({
  label,
  tone,
  checked,
  onChange,
}: {
  label: string;
  tone: string;
  checked: boolean;
  onChange: (b: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="w-full flex items-center justify-between gap-2 mt-2 group"
      aria-pressed={checked}
    >
      <span className="flex items-center gap-2">
        <span
          className="w-2 h-2 rounded-full"
          style={{ backgroundColor: checked ? tone : "rgba(250,250,247,0.18)" }}
        />
        <span
          className={`font-mono text-[10px] uppercase tracking-[0.18em] ${
            checked ? "text-bone-0" : "text-bone-3 group-hover:text-bone-1"
          }`}
        >
          {label}
        </span>
      </span>
      <span
        className={`font-mono text-[10px] tabular-nums ${
          checked ? "text-bone-1" : "text-bone-3"
        }`}
      >
        {checked ? "ON" : "off"}
      </span>
    </button>
  );
}

export default LevelsDropdown;
