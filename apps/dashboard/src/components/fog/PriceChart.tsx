"use client";

/* ------------------------------------------------------------------ */
/* PriceChart — lightweight-charts powered candle + overlay            */
/* ------------------------------------------------------------------ */
/*                                                                     */
/* /ES 0DTE intraday chart. Dummy deterministic data for now —          */
/* swap to live snapshot feed later (ohlc field on Snapshot is the      */
/* canonical source).                                                   */
/*                                                                     */
/* Theme matches the FLUX/FOG bone palette (locked):                    */
/*   bone-0  #F4EFE6                                                    */
/*   bone-2  #6B655B                                                    */
/*   bone-3  #45413B                                                    */
/*   ink     #14130F                                                    */
/*   crimson #B5002E                                                    */
/*   teal    #0FB5A8                                                    */
/* ------------------------------------------------------------------ */

import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";

const BASE = 5_840;

/** Generate deterministic 1m bars for an RTH session (09:30 → 16:00 ET). */
function genBars() {
  const bars: { time: Time; open: number; high: number; low: number; close: number }[] = [];
  // 09:30 ET on 2026-06-09 → epoch seconds (UTC = 13:30)
  const start = Math.floor(new Date("2026-06-09T13:30:00Z").getTime() / 1000);
  let prev = BASE;
  for (let i = 0; i < 390; i++) {
    // pseudo-random walk seeded by i
    const drift = Math.sin(i / 23) * 1.4 + Math.cos(i / 47) * 0.8;
    const noise = ((i * 9301 + 49297) % 233280) / 233280 - 0.5; // [-0.5, 0.5]
    const close = prev + drift + noise * 2.2;
    const open = prev;
    const high = Math.max(open, close) + Math.abs(noise) * 1.5;
    const low = Math.min(open, close) - Math.abs(noise) * 1.5;
    bars.push({
      time: (start + i * 60) as Time,
      open: +open.toFixed(2),
      high: +high.toFixed(2),
      low: +low.toFixed(2),
      close: +close.toFixed(2),
    });
    prev = close;
  }
  return bars;
}

/** VWAP overlay derived from candle midpoints (cheap proxy). */
function genVwap(bars: ReturnType<typeof genBars>) {
  let cumPV = 0;
  let cumV = 0;
  return bars.map((b) => {
    const tp = (b.high + b.low + b.close) / 3;
    const v = 1; // unit volume — dummy
    cumPV += tp * v;
    cumV += v;
    return { time: b.time, value: +(cumPV / cumV).toFixed(2) };
  });
}

export function PriceChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "#6B655B",
        fontFamily: "var(--font-jetbrains-mono), ui-monospace, monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(69, 65, 59, 0.15)" },
        horzLines: { color: "rgba(69, 65, 59, 0.15)" },
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

    const bars = genBars();

    // Candles
    const candles: ISeriesApi<"Candlestick"> = chart.addSeries(CandlestickSeries, {
      upColor: "#0FB5A8",
      downColor: "#B5002E",
      borderUpColor: "#0FB5A8",
      borderDownColor: "#B5002E",
      wickUpColor: "#0FB5A8",
      wickDownColor: "#B5002E",
    });
    candles.setData(bars);

    // VWAP overlay
    const vwap: ISeriesApi<"Line"> = chart.addSeries(LineSeries, {
      color: "#F4EFE6",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    vwap.setData(genVwap(bars));

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  return <div ref={containerRef} className="h-full w-full" />;
}
