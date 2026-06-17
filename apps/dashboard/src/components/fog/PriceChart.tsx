"use client";

/* ------------------------------------------------------------------ */
/* PriceChart — lightweight-charts candlestick from forward price      */
/* ------------------------------------------------------------------ */
/*                                                                     */
/* /ES 0DTE intraday chart. Builds candlesticks from the per-minute    */
/* forward price series (parity-derived). Each 1-minute bar:           */
/*   open  = previous minute's forward (or same for m=0)               */
/*   close = this minute's forward                                     */
/*   high  = max(open, close) + small noise to avoid flat bars         */
/*   low   = min(open, close) - small noise                            */
/*                                                                     */
/* Theme matches the FLUX/FOG bone palette (locked):                    */
/*   bone-0  #F4EFE6   bone-2  #6B655B   bone-3  #45413B               */
/*   ink     #14130F   crimson #B5002E   teal    #0FB5A8               */
/* ------------------------------------------------------------------ */

import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";

interface ForwardPoint {
  time: number;
  value: number;
}

export function PriceChart({
  forwardSeries = [],
}: {
  forwardSeries?: ForwardPoint[];
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  // Create the chart once.
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "#6B655B",
        fontFamily: "var(--font-jetbrains-mono), ui-monospace, monospace",
        fontSize: 10,
        attributionLogo: false,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      rightPriceScale: {
        borderColor: "rgba(69, 65, 59, 0.4)",
        textColor: "#6B655B",
      },
      timeScale: {
        borderColor: "rgba(69, 65, 59, 0.4)",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "#F4EFE6", width: 1, style: 3, labelBackgroundColor: "#14130F" },
        horzLine: { color: "#F4EFE6", width: 1, style: 3, labelBackgroundColor: "#14130F" },
      },
      autoSize: true,
    });
    chartRef.current = chart;

    // Candles — bone palette:
    //   up   → body bone-0 (putih tulang)         #F4EFE6
    //   down → body ink/black                     #000000
    //   border + wick → SEMUA bone-0 (outline putih tulang dua-duanya)
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#F4EFE6",
      downColor: "#000000",
      borderUpColor: "#F4EFE6",
      borderDownColor: "#F4EFE6",
      wickUpColor: "#F4EFE6",
      wickDownColor: "#F4EFE6",
    });
    seriesRef.current = candles;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Push data whenever the forward series changes.
  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart || forwardSeries.length === 0) return;

    // De-dupe + sort by time (lightweight-charts requires strictly ascending,
    // unique timestamps).
    const seen = new Set<number>();
    const sorted = forwardSeries
      .filter((p) => Number.isFinite(p.value) && p.time > 0)
      .sort((a, b) => a.time - b.time)
      .filter((p) => {
        if (seen.has(p.time)) return false;
        seen.add(p.time);
        return true;
      });

    // Build candles: open = previous close, high/low include both.
    const bars = sorted.map((p, i) => {
      const open = i > 0 ? sorted[i - 1].value : p.value;
      const close = p.value;
      const high = Math.max(open, close);
      const low = Math.min(open, close);
      const wickExt = Math.max(0.5, (high - low) * 0.15);
      return {
        time: p.time as Time,
        open: +open.toFixed(2),
        high: +(high + wickExt).toFixed(2),
        low: +(low - wickExt).toFixed(2),
        close: +close.toFixed(2),
      };
    });

    series.setData(bars);
    chart.timeScale().fitContent();
  }, [forwardSeries]);

  return <div ref={containerRef} className="h-full w-full" />;
}
