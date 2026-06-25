# Design: Live 1-min candles with 5s update (Fog chart)

## Goal
Fog chart candles (1-min) update every ~5s during formation — the in-progress
candle's body/wick moves live. Arc panel stays per-minute (unchanged).

## Approach (Option A — tick stream via new WS endpoint)
- Backend: `WS /ws/ticks?instrument=ES` streams front-future trade prices from
  `LiveBook._fut_trades` (already subscribed via the `trades` schema — no new
  Databento subscription, no worker cadence change).
- Frontend: `useLiveTicks(instrument)` hook subscribes, throttles to 5s, calls
  `series.update()` on lightweight-charts to refresh the current forming candle.
- Arc panel: unchanged (consumes per-minute snapshots).

## What does NOT change
- Worker cadence (still per-minute) — locked contract untouched.
- Arc panel (still per-minute).
- Snapshot schema_version 2.
- Replay path (still per-minute OHLC).

## Files
- services/api/src/api/ws.py — add `/ws/ticks` endpoint
- apps/dashboard/src/lib/useLiveTicks.ts — new hook
- apps/dashboard/src/components/fog/LevelsChartPanel.tsx — wire live candle update
