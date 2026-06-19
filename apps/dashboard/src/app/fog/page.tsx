"use client";

import { useMemo, useState } from "react";
import {
  StrikeGutter,
  MetricBarPanel,
  type SmilePoint,
} from "@/components/fog/panels";
import {
  buildStrikeModel,
  buildSmile,
  buildCallPutSmile,
  type StrikeDatum,
  type SviParams,
  type MetricKey,
  type CallPutSmilePoint,
} from "@/components/fog/strikeMath";
import { LevelsChartPanel } from "@/components/fog/LevelsChartPanel";
import { buildLevelsChart, type LevelsChartModel } from "@/components/fog/levelsChart";
import { buildFluxSeries, type FluxSeries } from "@/components/flux/fluxSeries";
import { ArcPanel } from "@/components/arc/ArcPanel";
import { TerminalShell } from "@/components/terminal/TerminalShell";
import { PanelRule, SegToggle, Toggle } from "@/components/terminal/chrome";
import { useTerminalFeed } from "@/lib/useTerminalFeed";
import type { Instrument, SnapshotSurface } from "@/lib/api";

/**
 * Fog — 0DTE GEX/DEX strike terminal (price/strike axis).
 *
 * Two zones inside the shared TerminalShell:
 *   - LEFT  : strike ladder + bidirectional per-strike bars (GEX or DEX, switch
 *             in the toolbar) + dotted IV-smile overlay (SVI, EXPERIMENTAL).
 *   - RIGHT : lightweight-charts price candles + selectable key levels (walls,
 *             per-strike Zero γ, largest GEX/DEX) + session-metrics strip.
 *
 * The feed (LIVE/REPLAY + ES/NQ + replay transport) is owned by the shell; this
 * page only adds the GEX|DEX + IV-smile toggles and the strike body.
 */

const DEFAULT_INSTRUMENT: Instrument = "ES";
const SESSION_DATE = "2026-06-09";

// Fallback synthetic strikes if the feed is fully offline (dev convenience).
function genSyntheticStrikes(): StrikeDatum[] {
  const STRIKE_COUNT = 24;
  const BASE_PRICE = 5_840;
  const TICK = 5;
  return Array.from({ length: STRIKE_COUNT }, (_, i) => {
    const price = BASE_PRICE + (STRIKE_COUNT - 1 - i) * TICK;
    const seed = (n: number) => {
      const t = Math.sin(i * 91.345 + n * 17.13) * 43758.5453;
      return t - Math.floor(t);
    };
    const mk = (a: number, b: number, c: number, d: number, e: number) => {
      const cur = (seed(a) - 0.5) * 2 * (0.4 + seed(b) * 0.6);
      const rng = 0.25 + seed(c) * 0.55;
      const lo = Math.max(-1, cur - rng * (0.3 + seed(d) * 0.7));
      const hi = Math.min(1, cur + rng * (0.3 + seed(e) * 0.7));
      return {
        current: cur,
        low: lo,
        high: hi,
        absCurrent: cur * 1e9,
        absLow: lo * 1e9,
        absHigh: hi * 1e9,
        diff5m: 100e6,
        diff30m: -200e6,
        diff60m: 150e6,
        diff5mNorm: (seed(a + 6) - 0.5) * 2,
      };
    };
    return { price, gex: mk(1, 2, 3, 4, 5), dex: mk(8, 9, 10, 11, 12) };
  });
}

export default function FogPage() {
  const feed = useTerminalFeed(DEFAULT_INSTRUMENT, SESSION_DATE);
  const { frames, status, latest, instrument } = feed;

  // IV-smile overlay toggle (default ON) + which per-strike metric the bars show.
  const [showSmile, setShowSmile] = useState(true);
  const [metric, setMetric] = useState<MetricKey>("gex");

  const forward = latest?.forward ?? 5872;

  const regime = useMemo<string>(() => {
    if (!latest) return "Neutral";
    const ng = latest.regime.net_gamma;
    return ng > 0 ? "Long Gamma" : ng < 0 ? "Short Gamma" : "Neutral";
  }, [latest]);

  // P/C ratio from flux (puts vs calls dealer delta-notional). Falls back to
  // 1.00 when flux is absent (contract-valid optional field).
  const pcRatio = useMemo<string>(() => {
    if (latest?.flux && latest.flux.calls !== 0) {
      return Math.abs(latest.flux.puts / latest.flux.calls).toFixed(2);
    }
    return "1.00";
  }, [latest]);

  // SVI surface: most recent non-null frame (the latest frame may be null).
  const surface = useMemo<SviParams | null>(() => {
    for (let i = frames.length - 1; i >= 0; i--) {
      const s: SnapshotSurface | null = frames[i].surface;
      if (s) return s;
    }
    return null;
  }, [frames]);

  // Build the full strike model (GEX + DEX + session min/max + momentum) at the
  // engine's native $5 spacing. Synthetic strikes ONLY when fully offline.
  const strikes = useMemo<StrikeDatum[]>(() => {
    if (frames.length > 0) return buildStrikeModel(frames).strikes;
    return status === "error" ? genSyntheticStrikes() : [];
  }, [frames, status]);

  // Price chart + selectable key levels + session metrics for the right panel.
  const levelsChart = useMemo<LevelsChartModel>(() => buildLevelsChart(frames), [frames]);

  // Cumulative HIRO flow series for the chart's lower pane (same time axis).
  const flux = useMemo<FluxSeries>(() => buildFluxSeries(frames), [frames]);

  // Self-normalized IV-smile curve (vol vs strike) from the SVI surface.
  const smile = useMemo<SmilePoint[] | null>(() => {
    if (!surface || strikes.length === 0) return null;
    return buildSmile(strikes, forward, surface);
  }, [surface, strikes, forward]);

  // Per-strike call/put IV smile (turquoise call / crimson put dots) from the
  // engine's `iv_smile` on the CURRENT frame — both sides on one shared scale so
  // the call-vs-put divergence reads directly. Preferred over the single SVI
  // smile when present; falls back to `smile` automatically inside the panel.
  const callPutSmile = useMemo<CallPutSmilePoint[] | null>(() => {
    if (strikes.length === 0) return null;
    return buildCallPutSmile(strikes, latest?.iv_smile);
  }, [strikes, latest]);

  // Major long/short strike (strongest current GEX each side) → gutter color.
  const majorLongPrice = useMemo(
    () => strikes.reduce((a, b) => (b.gex.current > a.gex.current ? b : a), strikes[0])?.price ?? 0,
    [strikes],
  );
  const majorShortPrice = useMemo(
    () => strikes.reduce((a, b) => (b.gex.current < a.gex.current ? b : a), strikes[0])?.price ?? 0,
    [strikes],
  );

  const metricLabel = metric.toUpperCase();

  return (
    <TerminalShell
      feed={feed}
      header={
        <StatsOverlay
          instrument={instrument}
          forward={forward}
          regime={regime}
          pcRatio={pcRatio}
          hasData={frames.length > 0}
        />
      }
    >
      {/* FOG section — first screen: LEFT strike stack + RIGHT price/levels. */}
      <section id="fog" className="relative flex h-screen w-full items-stretch px-8 pt-24 pb-20">
        <div className="flex basis-[26%] shrink-0 flex-col">
          {/* GEX/DEX + IV-smile controls sit right above the left strike stack. */}
          <div className="flex items-center gap-2 pb-2 pl-1">
            <SegToggle
              options={["GEX", "DEX"]}
              value={metricLabel}
              onChange={(v) => setMetric(v.toLowerCase() as MetricKey)}
            />
            <Toggle label="IV SMILE" on={showSmile} onClick={() => setShowSmile((v) => !v)} />
          </div>
          <div className="flex grow items-stretch overflow-y-auto overflow-x-hidden fog-scroll">
            <StrikeGutter
              strikes={strikes}
              forward={forward}
              majorLongPrice={majorLongPrice}
              majorShortPrice={majorShortPrice}
            />
            <PanelRule label={metricLabel} />
          <MetricBarPanel
            strikes={strikes}
            metric={metric}
            label={metricLabel}
            smile={smile}
            callPutSmile={callPutSmile}
            showSmile={showSmile}
          />
          </div>
        </div>
        <PanelRule label="PRICE · LEVELS" />
        <LevelsChartPanel model={levelsChart} flux={flux} className="grow" />
      </section>

      {/* ARC section — scroll down. 3D vol surface σ(K, session-time) reconstructed
          per minute from the engine's SVI fits; cursor marks the playhead minute. */}
      <section
        id="arc"
        className="relative flex min-h-screen w-full flex-col border-t border-rule px-8 py-12"
      >
        <div className="mb-4 flex items-baseline gap-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-bone-3">Arc · Volatility Surface</p>
          <p className="font-mono text-[10px] tracking-[0.2em] text-bone-3/50">
            σ(K, t) — drag to orbit · scroll to zoom · crimson cursor = playhead
          </p>
        </div>
        <ArcPanel frames={frames} playheadMinute={latest?.minute_index ?? -1} />
      </section>
    </TerminalShell>
  );
}

/* ------------------------------------------------------------------ */
/* StatsOverlay — top header strip (price · regime · P/C)              */
/* ------------------------------------------------------------------ */

function StatsOverlay({
  instrument,
  forward,
  regime,
  pcRatio,
  hasData,
}: {
  instrument: Instrument;
  forward: number;
  regime: string;
  pcRatio: string;
  hasData: boolean;
}) {
  const regimeColor =
    regime === "Long Gamma"
      ? "text-turquoise-deep"
      : regime === "Short Gamma"
        ? "text-crimson-deep"
        : "text-bone-3";

  const priceText = hasData
    ? forward.toLocaleString("en-US", { maximumFractionDigits: 2 })
    : "—";

  return (
    <div className="pointer-events-none fixed left-1/2 top-5 z-30 flex -translate-x-1/2 items-end gap-8">
      <div>
        <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-bone-3">/{instrument} Price</p>
        <p className="mt-0.5 font-mono text-[28px] font-medium leading-none tabular-nums text-amber-current">
          {priceText}
        </p>
      </div>
      <div>
        <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-bone-3">Gamma Regime</p>
        <p className={`mt-0.5 font-mono text-[13px] font-medium tracking-wide ${hasData ? regimeColor : "text-bone-3/50"}`}>
          {hasData ? regime : "—"}
        </p>
      </div>
      <div>
        <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-bone-3">P/C Ratio</p>
        <p className="mt-0.5 font-mono text-[13px] font-medium tabular-nums text-bone-0">
          {hasData ? pcRatio : "—"}
        </p>
      </div>
    </div>
  );
}
