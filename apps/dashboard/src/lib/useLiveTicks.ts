"use client";

/**
 * useLiveTicks — subscribes to `/ws/ticks` (or falls back to polling
 * `/api/snapshot` every 5 s) and feeds the current forming 1-min candle
 * back to a lightweight-charts `CandlestickSeries`.
 *
 * The candle array from the main snapshot feed remains the source of truth
 * for completed candles. This hook only calls `series.update()` on the
 * current candle so its body/wick moves live until the next minute closes
 * it and the snapshot feed replaces it with the finalized OHLC.
 */
import { useEffect, useRef } from "react";
import type { ISeriesApi, Time, CandlestickData } from "lightweight-charts";
import { snapshotUrlFor, wsTicksUrlFor, type Instrument } from "@/lib/api";

interface TickMsg {
  type: "tick";
  time: number;
  o: number;
  h: number;
  l: number;
  c: number;
  minute_index: number;
}

export function useLiveTicks(
  instrument: Instrument,
  series: ISeriesApi<"Candlestick"> | null,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const lastMinuteRef = useRef<number | null>(null);

  // Keep the series ref fresh across re-renders.
  useEffect(() => {
    seriesRef.current = series;
  }, [series]);

  useEffect(() => {
    if (!series || !instrument) return;
    let cancelled = false;

    // ---- Tier 1: WebSocket /ws/ticks (5s tick stream) ----
    const connectWs = () => {
      if (cancelled) return;
      let ws: WebSocket;
      try {
        ws = new WebSocket(wsTicksUrlFor(instrument));
      } catch {
        // Fall back to polling.
        startPolling();
        return;
      }
      wsRef.current = ws;

      ws.onmessage = (event) => {
        if (cancelled) return;
        try {
          const msg: TickMsg = JSON.parse(event.data as string);
          if (msg.type === "tick" && seriesRef.current) {
            const candle: CandlestickData = {
              time: msg.time as Time,
              open: msg.o,
              high: msg.h,
              low: msg.l,
              close: msg.c,
            };
            seriesRef.current.update(candle);
            lastMinuteRef.current = msg.minute_index;
          }
        } catch {
          /* ignore non-JSON frames */
        }
      };

      ws.onclose = () => {
        if (cancelled) return;
        wsRef.current = null;
        startPolling();
      };

      ws.onerror = () => {
        try { ws.close(); } catch { /* already closing */ }
      };
    };

    // ---- Tier 2: REST polling fallback ----
    const startPolling = () => {
      if (cancelled || pollRef.current) return;
      pollRef.current = setInterval(async () => {
        try {
          const res = await fetch(snapshotUrlFor(instrument as any), { credentials: "include" });
          if (!res.ok) return;
          const snap = await res.json();
          if (cancelled) return;
          if (!snap?.forward) return;
          const f = snap.forward as number;
          const minuteIdx = snap.minute_index as number | undefined;
          const ts = snap.ts as string | undefined;
          const time: Time = (ts ? Math.floor(new Date(ts).getTime() / 1000) : Math.floor(Date.now() / 1000)) as Time;
          const ohlc = snap.ohlc as { open?: number; high?: number; low?: number; close?: number } | null;
          const candle: CandlestickData = {
            time,
            open: ohlc?.open ?? f,
            high: ohlc?.high ?? f,
            low: ohlc?.low ?? f,
            close: f,
          };
          if (seriesRef.current) {
            seriesRef.current.update(candle);
            if (minuteIdx != null) lastMinuteRef.current = minuteIdx;
          }
        } catch {
          /* network error, retry next interval */
        }
      }, 5000);
    };

    connectWs();

    return () => {
      cancelled = true;
      if (wsRef.current) {
        try { wsRef.current.close(); } catch { /* ignore */ }
        wsRef.current = null;
      }
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [instrument, series]);
}
