"use client";

import { useEffect, useRef, useState } from "react";
import { PriceChart } from "@/components/fog/PriceChart";

/**
 * Fog — 0DTE GEX/DEX terminal landing surface.
 *
 * Layout principles (per design spec, 2026-06-16 rev2):
 *   - Minimalism: no heavy borders. Hairline rules separate the three zones
 *     (price ladder | GEX profile | chart). Bar pills are rounded, not boxy.
 *   - Selector dropdown (top-left): GEX / VEX / CEX / DEX. Click opens, click
 *     item selects, click-outside closes. Hover text → red.
 *   - GEX profile (left rail):
 *       · Each row = one strike. Background hairline = full historical
 *         GEX range (low ↔ high). Foreground pill = current GEX value.
 *       · Pills are rounded-full (lozenge), bidirectional from a center axis.
 *       · Center vertical line = zero-axis.
 *       · Rows are tightly packed but visibly separated.
 *       · Color: deep turquoise = long GEX, deep crimson = short GEX.
 *   - Price ladder (leftmost): font-color only (no fill).
 *       · Amber  = current price
 *       · Turquoise = level with major net long GEX
 *       · Crimson   = level with major net short GEX
 *   - Center: chart placeholder.
 *   - Right rail: turquoise→black→crimson heatmap gradient.
 *   - Bottom-left: flash glyph.
 *
 * All synthetic data is deterministic (seeded) — SSR ↔ client identical.
 */

const SELECTORS = ["GEX", "VEX", "CEX", "DEX"] as const;
type Selector = (typeof SELECTORS)[number];

// ── Synthetic GEX-by-strike profile ────────────────────────────────
//   24 strikes spanning the simulated price range. Each strike has:
//     · current  : signed GEX value in [-1, 1]
//     · low      : historical minimum (≤ current)
//     · high     : historical maximum (≥ current)
//   Seeded so SSR = client. Strike count is even for clean visual.
const STRIKE_COUNT = 24;
const BASE_PRICE = 5_840;
const TICK = 5;
const CURRENT_PRICE = 5_872; // amber row
const STRIKES = Array.from({ length: STRIKE_COUNT }, (_, i) => {
  const price = BASE_PRICE + (STRIKE_COUNT - 1 - i) * TICK; // top = highest price
  const seed = (n: number) => {
    const t = Math.sin(i * 91.345 + n * 17.13) * 43758.5453;
    return t - Math.floor(t);
  };
  const current = (seed(1) - 0.5) * 2 * (0.4 + seed(2) * 0.6); // [-1, 1]
  const range = 0.25 + seed(3) * 0.55;
  const low = Math.max(-1, current - range * (0.3 + seed(4) * 0.7));
  const high = Math.min(1, current + range * (0.3 + seed(5) * 0.7));
  return { price, current, low, high };
});

// Major long/short levels = the two extremes of |current|.
const MAJOR_LONG_PRICE = STRIKES.reduce((a, b) =>
  b.current > a.current ? b : a,
).price;
const MAJOR_SHORT_PRICE = STRIKES.reduce((a, b) =>
  b.current < a.current ? b : a,
).price;

export default function FogPage() {
  const [selector, setSelector] = useState<Selector>("GEX");
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  // Close dropdown on outside click / Escape
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!dropdownRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-black text-bone-0">
      {/* Top-center banner */}
      <div className="pointer-events-none fixed inset-x-0 top-9 z-40 flex justify-center">
        <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-bone-3">
          FlowDesk · Zero-DTE GEX / DEX Terminal
        </p>
      </div>

      {/* Selector dropdown — top-left */}
      <div ref={dropdownRef} className="fixed left-8 top-[4.5rem] z-40">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="font-mono text-[13px] tracking-[0.18em] text-bone-0 transition-colors duration-150 hover:text-brick-glow"
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          {selector}
        </button>
        {open && (
          <ul
            role="listbox"
            className="absolute left-0 top-6 flex flex-col gap-1.5 font-mono text-[13px] tracking-[0.18em]"
          >
            {SELECTORS.filter((s) => s !== selector).map((s) => (
              <li key={s}>
                <button
                  type="button"
                  role="option"
                  aria-selected={false}
                  onClick={() => {
                    setSelector(s);
                    setOpen(false);
                  }}
                  className="text-bone-3 transition-colors duration-150 hover:text-brick-glow"
                >
                  {s}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Main grid: price | rule | GEX profile | rule | chart | rule | gradient */}
      <div className="flex h-screen w-full items-stretch gap-0 px-8 pt-24 pb-20">
        <PriceLadder />
        <div className="mx-3 w-px bg-rule" aria-hidden="true" />
        <GexProfile />
        <div className="mx-3 w-px bg-rule" aria-hidden="true" />
        <div className="relative flex flex-1 flex-col">
          {/* Stats banner — fixed di atas chart area */}
          <StatsBanner />
          {/* Chart placeholder di bawah */}
          <PriceChart />
        </div>
        <div className="mx-3 w-px bg-rule" aria-hidden="true" />
        <GradientRail />
      </div>

      {/* Bottom-left flash glyph */}
      <button
        type="button"
        aria-label="Quick action"
        className="fixed bottom-7 left-8 z-40 text-bone-3 transition-colors duration-150 hover:text-brick-glow"
      >
        <FlashIcon />
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Price ladder — font-color only                                      */
/* ------------------------------------------------------------------ */

function PriceLadder() {
  return (
    <div className="flex w-16 flex-col justify-between py-1 pr-2 text-right">
      {STRIKES.map((s) => {
        const isCurrent = Math.abs(s.price - CURRENT_PRICE) < TICK / 2;
        const isLong = s.price === MAJOR_LONG_PRICE;
        const isShort = s.price === MAJOR_SHORT_PRICE;
        const cls = isCurrent
          ? "text-amber-current"
          : isLong
            ? "text-turquoise-deep"
            : isShort
              ? "text-crimson-deep"
              : "text-bone-3";
        return (
          <span
            key={s.price}
            className={`font-mono text-[10.5px] leading-none tracking-tight tabular-nums ${cls}`}
          >
            {s.price.toLocaleString("en-US")}
          </span>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* GEX profile — bidirectional rounded pills + history range hairline  */
/* ------------------------------------------------------------------ */

function GexProfile() {
  return (
    <div className="relative flex w-80 flex-col justify-between py-0.5 pl-3 pr-3">
      {/* Center zero-axis */}
      <div className="pointer-events-none absolute inset-y-0.5 left-1/2 w-px -translate-x-1/2 bg-rule" />

      {STRIKES.map((s, i) => (
        <GexRow key={i} current={s.current} low={s.low} high={s.high} />
      ))}
    </div>
  );
}

function GexRow({
  current,
  low,
  high,
}: {
  current: number;
  low: number;
  high: number;
}) {
  // Convert [-1, 1] → percent offset from center.
  const pct = (v: number) => `${(v * 50).toFixed(2)}%`;
  const positive = current >= 0;
  const color = positive ? "bg-turquoise-deep" : "bg-crimson-deep";

  // Pill geometry
  const pillLeft = positive ? "50%" : `calc(50% + ${pct(current)})`;
  const pillWidth = `${(Math.abs(current) * 50).toFixed(2)}%`;

  // Range hairline (low↔high) — spans negative/positive freely
  const rangeLeft = `calc(50% + ${pct(low)})`;
  const rangeWidth = `${((high - low) * 50).toFixed(2)}%`;

  return (
    <div className="relative flex h-[13px] w-full items-center">
      {/* History range hairline — sits behind pill, LEBIH TERANG */}
      <div
        className="absolute h-px bg-bone-3/40"
        style={{ left: rangeLeft, width: rangeWidth }}
      />
      {/* Current GEX pill — LEBIH BESAR */}
      <div
        className={`absolute h-[9px] rounded-full ${color}`}
        style={{ left: pillLeft, width: pillWidth }}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Stats banner — realtime price, gamma regime, P/C ratio (top bar)    */
/* ------------------------------------------------------------------ */

function StatsBanner() {
  // Mock realtime stats (deterministic seed untuk SSR)
  const currentPrice = CURRENT_PRICE;
  const priceChange = -12.5; // points since RTH open
  const priceChangePct = (priceChange / currentPrice) * 100;
  
  // Gamma regime classification based on net GEX
  const netGex = STRIKES.reduce((sum, s) => sum + s.current, 0);
  const gammaRegime = netGex > 0.5 ? "Long Gamma" : netGex < -0.5 ? "Short Gamma" : "Neutral";
  const regimeColor = netGex > 0.5 ? "text-turquoise-deep" : netGex < -0.5 ? "text-crimson-deep" : "text-bone-3";
  
  const totalCallOI = 142_300;
  const totalPutOI = 138_900;
  const pcRatio = (totalPutOI / totalCallOI).toFixed(2);

  return (
    <div className="flex w-full shrink-0 items-baseline gap-6 border-b border-rule px-6 pb-3 pt-2">
      <div>
        <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-bone-3">
          /ES Price
        </p>
        <p className="mt-0.5 font-mono text-[28px] font-medium leading-none tabular-nums text-amber-current">
          {currentPrice.toLocaleString("en-US")}
        </p>
        <p className={`mt-0.5 font-mono text-[10px] tabular-nums ${priceChange < 0 ? "text-crimson-deep" : "text-turquoise-deep"}`}>
          {priceChange > 0 ? "+" : ""}{priceChange.toFixed(1)} ({priceChangePct > 0 ? "+" : ""}{priceChangePct.toFixed(2)}%)
        </p>
      </div>
      <div>
        <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-bone-3">
          Gamma Regime
        </p>
        <p className={`mt-0.5 font-mono text-[16px] font-medium tracking-wide ${regimeColor}`}>
          {gammaRegime}
        </p>
      </div>
      <div>
        <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-bone-3">
          P/C Ratio
        </p>
        <p className="mt-0.5 font-mono text-[16px] font-medium tabular-nums text-bone-0">
          {pcRatio}
        </p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Gradient rail                                                       */
/* ------------------------------------------------------------------ */

function GradientRail() {
  return (
    <div className="relative flex h-full w-7 flex-col overflow-hidden rounded-[6px]">
      <div
        className="h-full w-full"
        style={{
          background:
            "linear-gradient(to bottom, #0FB5A8 0%, #000000 50%, #B5002E 100%)",
        }}
      />
      <div className="pointer-events-none absolute inset-0 flex flex-col justify-between py-[10%]">
        {Array.from({ length: 9 }).map((_, i) => (
          <div key={i} className="h-px w-full bg-black/40" />
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Icons                                                               */
/* ------------------------------------------------------------------ */

function FlashIcon() {
  return (
    <svg
      width="18"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}
