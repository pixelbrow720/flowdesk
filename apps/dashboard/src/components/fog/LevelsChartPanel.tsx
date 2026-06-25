"use client";

/* ------------------------------------------------------------------ */
/* LevelsChartPanel — right: price candles + selectable key levels      */
/* ------------------------------------------------------------------ */
/*                                                                      */
/* A clean price chart (lightweight-charts candlesticks of the spot)    */
/* with the engine's key levels drawn as horizontal price lines you can */
/* toggle on/off via the chip row, plus a session metrics strip below.  */
/*                                                                      */
/*   candles → spot/forward OHLC (1-min)                                */
/*   levels  → call/put wall, γ flip, largest GEX/DEX (real) +          */
/*             hedge wall, abs γ, OI γ flip (EXPERIMENTAL, off by       */
/*             default)                                                  */
/*   metrics → ATM IV · Exp Move · Net γ · GEX+ share · Skew            */
/*                                                                      */
/* EXPERIMENTAL levels/metrics are unvalidated (AGENTS.md gap #1).      */

import { useEffect, useMemo, useRef, useState } from "react";
import { useLiveTicks } from "@/lib/useLiveTicks";
import {
  createChart,
  CandlestickSeries,
  BaselineSeries,
  LineSeries,
  CrosshairMode,
  LineStyle,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import type { LevelsChartModel, SessionMetrics } from "@/components/fog/levelsChart";
import type { FluxSeries } from "@/components/flux/fluxSeries";
import { DropdownChecklist, type ChecklistItem } from "@/components/terminal/chrome";
import type { Instrument } from "@/lib/api";

// Levels shown by default (the non-experimental ones).
const DEFAULT_ON = new Set(["call_wall", "put_wall", "gamma_flip"]);

// Toggleable ratio overlays (own hidden price scale each, so the candle scale
// is never distorted). Default OFF — opt-in to keep the chart clean.
const OVERLAYS = [
  { id: "gexShare", label: "GEX+ %", color: "#5BA3D0", scaleId: "ov_gex", exp: false },
  { id: "atmVol", label: "ATM IV", color: "#D9534F", scaleId: "ov_atm", exp: true },
  { id: "skew", label: "Skew", color: "#8E8E88", scaleId: "ov_skew", exp: true },
] as const;

// FLUX decomposition lines drawn in the lower pane (calls/puts/retail). The
// `total` HIRO line is always shown as the baseline; these are opt-in.
const FLUX_LINES = [
  { id: "fcalls", key: "calls", label: "Flux Calls", color: "#0FB5A8" },
  { id: "fputs", key: "puts", label: "Flux Puts", color: "#B5002E" },
  { id: "fretail", key: "retail", label: "Flux Retail", color: "#C8A24A" },
] as const;

export function LevelsChartPanel({
  instrument,
  model,
  flux,
  className = "flex-1",
}: {
  instrument: Instrument;
  model: LevelsChartModel;
  flux?: FluxSeries;
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  // One hidden-scale line series per ratio overlay, keyed by overlay id.
  const overlayRef = useRef<Record<string, ISeriesApi<"Line">>>({});
  // FLUX lower pane: the HIRO baseline + the decomposition lines.
  const fluxBaseRef = useRef<ISeriesApi<"Baseline"> | null>(null);
  const fluxLineRef = useRef<Record<string, ISeriesApi<"Line">>>({});

  // Which level ids are visible. Initialize to defaults that actually exist.
  const [active, setActive] = useState<Set<string>>(() => new Set(DEFAULT_ON));
  // Which ratio overlays are visible (all off by default).
  const [overlays, setOverlays] = useState<Set<string>>(() => new Set());
  // Which FLUX decomposition lines are visible (all off by default; the HIRO
  // baseline `total` is always drawn).
  const [fluxLines, setFluxLines] = useState<Set<string>>(() => new Set());

  // Create the chart + candle series once.
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "#8E8E88",
        fontFamily: "var(--font-jetbrains-mono), ui-monospace, monospace",
        fontSize: 10,
        attributionLogo: false,
        // Pane separator (between price candles + flux): thin dark grey, not the
        // bright default (#2B2B43 reads almost white on the black terminal).
        panes: {
          separatorColor: "rgba(142,142,136,0.18)",
          separatorHoverColor: "rgba(142,142,136,0.35)",
          enableResize: true,
        },
      },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      rightPriceScale: { borderColor: "rgba(142,142,136,0.25)" },
      timeScale: {
        borderColor: "rgba(142,142,136,0.25)",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "#FAFAF7", width: 1, style: LineStyle.Dotted, labelBackgroundColor: "#000000" },
        horzLine: { color: "#FAFAF7", width: 1, style: LineStyle.Dotted, labelBackgroundColor: "#000000" },
      },
      autoSize: true,
    });
    chartRef.current = chart;
    seriesRef.current = chart.addSeries(CandlestickSeries, {
      upColor: "#FAFAF7",
      downColor: "#000000",
      borderUpColor: "#FAFAF7",
      borderDownColor: "#FAFAF7",
      wickUpColor: "#FAFAF7",
      wickDownColor: "#FAFAF7",
    });

    // Ratio overlays: each on its OWN hidden price scale so the candle scale
    // is never rescaled by a 0..100 / vol series. Visibility toggled later.
    overlayRef.current = {};
    for (const ov of OVERLAYS) {
      overlayRef.current[ov.id] = chart.addSeries(LineSeries, {
        color: ov.color,
        lineWidth: 1,
        priceScaleId: ov.scaleId,
        lastValueVisible: false,
        priceLineVisible: false,
        visible: false,
        crosshairMarkerVisible: false,
      });
      chart.priceScale(ov.scaleId).applyOptions({ visible: false, scaleMargins: { top: 0.1, bottom: 0.1 } });
    }

    // FLUX lower pane (paneIndex 1): the cumulative HIRO line as a baseline
    // anchored at 0 (turquoise above = net dealer buying, crimson below =
    // selling), sharing the SAME time axis as the candles above. Decomposition
    // lines (calls/puts/retail) live in the same pane, hidden until toggled.
    fluxBaseRef.current = chart.addSeries(
      BaselineSeries,
      {
        baseValue: { type: "price", price: 0 },
        topLineColor: "#0FB5A8",
        topFillColor1: "rgba(15,181,168,0.28)",
        topFillColor2: "rgba(15,181,168,0.02)",
        bottomLineColor: "#B5002E",
        bottomFillColor1: "rgba(181,0,46,0.02)",
        bottomFillColor2: "rgba(181,0,46,0.28)",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: false,
      },
      1,
    );
    fluxLineRef.current = {};
    for (const ln of FLUX_LINES) {
      fluxLineRef.current[ln.id] = chart.addSeries(
        LineSeries,
        {
          color: ln.color,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          visible: false,
          crosshairMarkerVisible: false,
        },
        1,
      );
    }
    // Split the height: ~62% price candles, ~38% flux.
    const panes = chart.panes();
    if (panes.length >= 2) {
      panes[0].setStretchFactor(62);
      panes[1].setStretchFactor(38);
    }

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      priceLinesRef.current = [];
      overlayRef.current = {};
      fluxBaseRef.current = null;
      fluxLineRef.current = {};
    };
  }, []);

  // Live candle updates: poll /ws/ticks every 5s to refresh the in-progress
  // 1-min candle (body/wick moves live). Arc panel is unaffected (per-minute).
  const [liveSeries, setLiveSeries] = useState<ISeriesApi<"Candlestick"> | null>(null);
  useEffect(() => {
    setLiveSeries(seriesRef.current);
  }, []);
  useLiveTicks(instrument, liveSeries);

  // Feed candles + overlay data when the model changes.
  useEffect(() => {
    const s = seriesRef.current;
    const chart = chartRef.current;
    if (!s || !chart || model.candles.length === 0) return;
    s.setData(model.candles.map((c) => ({ ...c, time: c.time as Time })));
    const ov = overlayRef.current;
    ov.gexShare?.setData(model.ratios.gexLongShare.map((p) => ({ time: p.time as Time, value: p.value })));
    ov.atmVol?.setData(model.ratios.atmVol.map((p) => ({ time: p.time as Time, value: p.value })));
    ov.skew?.setData(model.ratios.skew.map((p) => ({ time: p.time as Time, value: p.value })));
    chart.timeScale().fitContent();
  }, [model]);

  // Feed the FLUX lower pane (HIRO baseline + decomposition) when flux changes.
  useEffect(() => {
    const base = fluxBaseRef.current;
    if (!base || !flux) return;
    base.setData(flux.total.map((p) => ({ time: p.time as Time, value: p.value })));
    for (const ln of FLUX_LINES) {
      const series = fluxLineRef.current[ln.id];
      const data = flux[ln.key as "calls" | "puts" | "retail"];
      series?.setData(data.map((p) => ({ time: p.time as Time, value: p.value })));
    }
  }, [flux]);

  // Toggle FLUX decomposition line visibility.
  useEffect(() => {
    for (const ln of FLUX_LINES) {
      fluxLineRef.current[ln.id]?.applyOptions({ visible: fluxLines.has(ln.id) });
    }
  }, [fluxLines]);

  // Toggle overlay series visibility.
  useEffect(() => {
    for (const ov of OVERLAYS) {
      overlayRef.current[ov.id]?.applyOptions({ visible: overlays.has(ov.id) });
    }
  }, [overlays]);

  // Redraw price lines whenever the model or the active set changes.
  useEffect(() => {
    const s = seriesRef.current;
    if (!s) return;
    for (const pl of priceLinesRef.current) s.removePriceLine(pl);
    priceLinesRef.current = [];
    for (const lv of model.levels) {
      if (!active.has(lv.id)) continue;
      priceLinesRef.current.push(
        s.createPriceLine({
          price: lv.price,
          color: lv.color,
          lineWidth: 1,
          lineStyle: lv.experimental ? LineStyle.Dotted : LineStyle.Dashed,
          axisLabelVisible: true,
          title: lv.label,
        }),
      );
    }
  }, [model, active]);

  const toggle = (id: string) =>
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const toggleOverlay = (id: string) =>
    setOverlays((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const toggleFluxLine = (id: string) =>
    setFluxLines((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <div className={`relative flex min-w-0 flex-col ${className}`}>
      {/* Compact control row: three dropdowns instead of a long chip wall. */}
      <div className="flex flex-wrap items-center gap-2 px-1 pb-2">
        <DropdownChecklist
          label="Key Levels"
          items={model.levels.map((lv): ChecklistItem => ({
            id: lv.id,
            label: lv.label,
            color: lv.color,
            experimental: lv.experimental,
          }))}
          active={active}
          onToggle={toggle}
        />
        <DropdownChecklist
          label="Ratios"
          items={OVERLAYS.map((ov): ChecklistItem => ({
            id: ov.id,
            label: ov.label,
            color: ov.color,
            experimental: ov.exp,
          }))}
          active={overlays}
          onToggle={toggleOverlay}
        />
        {flux && (
          <DropdownChecklist
            label="Flux"
            items={FLUX_LINES.map((ln): ChecklistItem => ({
              id: ln.id,
              label: ln.label.replace("Flux ", ""),
              color: ln.color,
            }))}
            active={fluxLines}
            onToggle={toggleFluxLine}
          />
        )}
      </div>

      {/* Candle chart with the price lines + ratio overlays. */}
      <div ref={containerRef} className="min-h-0 flex-1" />

      {/* Session metrics strip. */}
      <MetricsStrip metrics={model.metrics} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* MetricsStrip — latest session metrics (overlay strip below chart)   */
/* ------------------------------------------------------------------ */

function fmtNotional(v: number): string {
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "+";
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(0)}M`;
  return `${sign}$${abs.toFixed(0)}`;
}

/* ------------------------------------------------------------------ */
/* MetricsStrip — latest session metrics (overlay strip below chart)   */
/* ------------------------------------------------------------------ */

// SessionMetrics now carries the 3 EXPERIMENTAL lenses (thetaDecay, maxPain,
// volExpansion) as optional fields, so MetricsStrip can consume the type
// directly without an extra wrapper.

function MetricsStrip({ metrics }: { metrics: SessionMetrics }) {
  const items = useMemo(
    () => [
      { label: "ATM IV", value: metrics.atmVol != null ? `${(metrics.atmVol * 100).toFixed(1)}%` : "—", exp: true },
      { label: "EXP MOVE", value: metrics.expectedMove != null ? `±${metrics.expectedMove.toFixed(0)}` : "—", exp: true },
      {
        label: "NET γ",
        value: metrics.netGamma != null ? fmtNotional(metrics.netGamma) : "—",
        tone: metrics.netGamma != null ? (metrics.netGamma >= 0 ? "pos" : "neg") : undefined,
        exp: false,
      },
      {
        label: "NET θ/DAY",
        value: metrics.thetaDecay != null ? fmtNotional(metrics.thetaDecay) : "—",
        tone: metrics.thetaDecay != null ? (metrics.thetaDecay >= 0 ? "pos" : "neg") : undefined,
        exp: true,
      },
      {
        label: "MAX PAIN",
        value: metrics.maxPain != null ? metrics.maxPain.toFixed(0) : "—",
        exp: true,
      },
      {
        label: "VOL σ-SPREAD",
        value: metrics.volExpansion != null ? metrics.volExpansion.toFixed(3) : "—",
        exp: true,
      },
      { label: "SKEW", value: metrics.skew != null ? metrics.skew.toFixed(2) : "—", exp: true },
    ],
    [metrics],
  );

  return (
    <div className="flex items-stretch gap-6 border-t border-rule px-2 pt-2.5">
      {items.map((it) => (
        <div key={it.label} className="flex flex-col gap-0.5">
          <span className="font-mono text-[8px] uppercase tracking-[0.25em] text-bone-3/70">
            {it.label}
            {it.exp && <span className="ml-1 text-bone-3/40">EXP</span>}
          </span>
          <span
            className={`font-mono text-[13px] tabular-nums ${
              it.tone === "pos"
                ? "text-turquoise-deep"
                : it.tone === "neg"
                  ? "text-crimson-deep"
                  : "text-bone-0"
            }`}
          >
            {it.value}
          </span>
        </div>
      ))}
    </div>
  );
}
