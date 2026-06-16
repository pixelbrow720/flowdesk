/**
 * FOG — positioning lens. TRACE-style 2-column layout (25% / 75%).
 *
 * Layout (placeholder data; engine wiring later):
 *   Row 1: Spot · Regime · GEX · DEX · IV%-ile
 *   Row 2: GammaProfile vertical [span 3] · Candlestick + Levels [span 9]
 *   Row 3: Call walls top-3 [span 6] · Put walls top-3 [span 6]
 *   Row 4: 0DTE expiry · Snapshot age · Session state
 *
 * NOTE: All numbers di file ini DUMMY — diganti `Snapshot` payload dari
 * /api/snapshot/{instrument} saat data wiring fase.
 */

import { FogRow2 } from "@/components/fog/fog-row-2";
import { WallsList } from "@/components/fog/walls-list";
import { StatTile } from "@/components/fog/stat-tile";
import { RegimeBadge } from "@/components/fog/regime-badge";
import type { Candle } from "@/components/fog/price-chart";

// ─── DUMMY DATA ─────────────────────────────────────────────────
const FAKE = {
  instrument: "ES" as const,
  spot: 5847.25,
  spotChangePct: +0.42,
  regime: "long-gamma" as "long-gamma" | "short-gamma",
  flipLevel: 5832.5,
  gex: 12.4e9,
  gexChange: +1.8e9,
  dex: -3.2e9,
  ivPercentile: 23,
  atmIv: 0.118,
  callWalls: [
    { strike: 5875, gammaDollar: 4.2e9 },
    { strike: 5900, gammaDollar: 3.1e9 },
    { strike: 5860, gammaDollar: 2.7e9 },
  ],
  putWalls: [
    { strike: 5825, gammaDollar: 3.6e9 },
    { strike: 5800, gammaDollar: 2.9e9 },
    { strike: 5840, gammaDollar: 2.1e9 },
  ],
  gammaProfile: generateGammaProfile(5847.25),
  candles: generateCandles(5847.25),
  expirySecondsToClose: 4 * 3600 + 23 * 60 + 12,
  snapshotAgeSec: 42,
  sessionState: "RTH" as const,
};

function generateGammaProfile(spot: number) {
  // Strikes kelipatan 5, range ±50 around spot → 21 strikes
  const strikes: { strike: number; gamma: number }[] = [];
  const center = Math.round(spot / 5) * 5;
  for (let k = -50; k <= 50; k += 5) {
    const strike = center + k;
    const distance = Math.abs(k);
    const magnitude = Math.exp(-distance * distance / 600) * 1e9;
    const sign = k > 0 ? +1 : -1; // calls above, puts below
    const noise = (Math.sin(k * 0.31) * 0.3 + 1) * sign;
    strikes.push({ strike, gamma: magnitude * noise });
  }
  return strikes;
}

function generateCandles(spot: number): Candle[] {
  // 120 × 1-min candles, mean-revert toward spot, deterministic
  const candles: Candle[] = [];
  let prev = spot - 8;
  const start = Date.now() - 120 * 60_000;
  for (let i = 0; i < 120; i++) {
    const seedA = Math.sin(i * 0.37);
    const seedB = Math.cos(i * 0.91) * 0.6;
    const drift = (spot - prev) * 0.02;
    const open = parseFloat(prev.toFixed(2));
    const close = parseFloat((open + seedA * 0.5 + seedB * 0.4 + drift).toFixed(2));
    // High/low: extremes around open/close, with intra-bar noise
    const wickUp = Math.abs(Math.sin(i * 1.13)) * 0.7;
    const wickDn = Math.abs(Math.cos(i * 0.71)) * 0.7;
    const hi = parseFloat((Math.max(open, close) + wickUp).toFixed(2));
    const lo = parseFloat((Math.min(open, close) - wickDn).toFixed(2));
    candles.push({ t: start + i * 60_000, o: open, h: hi, l: lo, c: close });
    prev = close;
  }
  // Force last candle close to current spot (so SPOT line lands on last bar)
  const last = candles[candles.length - 1];
  candles[candles.length - 1] = {
    ...last,
    c: spot,
    h: Math.max(last.h, spot),
    l: Math.min(last.l, spot),
  };
  return candles;
}

export default function FogPage() {
  const d = FAKE;
  return (
    <div className="px-5 py-5">
      {/* Eyebrow */}
      <div className="flex items-center gap-3 mb-4">
        <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3">
          Lens · Positioning
        </span>
        <span className="h-px flex-1 bg-[color:var(--hairline)]" />
        <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3 tabular-nums">
          /{d.instrument} · 0DTE
        </span>
      </div>

      {/* Row 1 — hero stats */}
      <div className="grid grid-cols-12 gap-3 mb-3">
        <StatTile
          className="col-span-3"
          label="Spot"
          primary={d.spot.toFixed(2)}
          delta={d.spotChangePct}
          deltaFmt="pct"
        />
        <div className="col-span-3 border border-[color:var(--hairline)] p-4 flex flex-col justify-between">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3">
            Regime
          </span>
          <div className="flex items-end justify-between">
            <RegimeBadge regime={d.regime} />
            <span className="font-mono text-[10px] tabular-nums text-bone-3">
              flip {d.flipLevel.toFixed(2)}
            </span>
          </div>
        </div>
        <StatTile
          className="col-span-2"
          label="GEX (1%)"
          primary={formatBn(d.gex)}
          delta={d.gexChange / 1e9}
          deltaFmt="bn"
        />
        <StatTile
          className="col-span-2"
          label="DEX"
          primary={formatBn(d.dex)}
        />
        <StatTile
          className="col-span-2"
          label="IV %-ile"
          primary={`${d.ivPercentile}`}
          secondary={`atm ${(d.atmIv * 100).toFixed(1)}%`}
        />
      </div>

      {/* Row 2 — TRACE-style: GEX profile vertical (25%) + candlestick (75%) */}
      <FogRow2
        gammaProfile={d.gammaProfile}
        candles={d.candles}
        callWalls={d.callWalls}
        putWalls={d.putWalls}
        spot={d.spot}
        flip={d.flipLevel}
        instrument={d.instrument}
      />

      {/* Row 3 — walls list */}
      <div className="grid grid-cols-12 gap-3 mb-3">
        <div className="col-span-6 border border-[color:var(--hairline)] p-4">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3 block mb-3">
            Call walls · top 3 · γ$
          </span>
          <WallsList rows={d.callWalls} side="call" />
        </div>
        <div className="col-span-6 border border-[color:var(--hairline)] p-4">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3 block mb-3">
            Put walls · top 3 · γ$
          </span>
          <WallsList rows={d.putWalls} side="put" />
        </div>
      </div>

      {/* Row 4 — meta strip */}
      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-4 border border-[color:var(--hairline)] p-4">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3 block mb-2">
            0DTE expiry
          </span>
          <span className="font-mono text-[18px] tabular-nums text-bone-0">
            {formatCountdown(d.expirySecondsToClose)}
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3 block mt-1">
            until 16:00 ET
          </span>
        </div>
        <div className="col-span-4 border border-[color:var(--hairline)] p-4">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3 block mb-2">
            Snapshot age
          </span>
          <span className="font-mono text-[18px] tabular-nums text-bone-0">
            {d.snapshotAgeSec}s
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3 block mt-1">
            cadence 60s · schema v1
          </span>
        </div>
        <div className="col-span-4 border border-[color:var(--hairline)] p-4">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3 block mb-2">
            Session state
          </span>
          <span className="font-mono text-[18px] uppercase tracking-[0.1em] text-bone-0">
            {d.sessionState}
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3 block mt-1">
            real-time clock · ET
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── helpers ────────────────────────────────────────────────────
function formatBn(n: number): string {
  const sign = n < 0 ? "−" : "";
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  return `${sign}$${abs.toFixed(0)}`;
}
function formatCountdown(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${h}h ${m.toString().padStart(2, "0")}m ${sec.toString().padStart(2, "0")}s`;
}
