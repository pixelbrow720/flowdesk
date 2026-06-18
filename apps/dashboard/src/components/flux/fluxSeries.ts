/**
 * fluxSeries — pure helpers for the Flux lens (HIRO-style time-series flow).
 *
 * The engine emits, per minute, a `flux` block of dealer delta-notional (USD)
 * accumulated since the RTH open:
 *   { total, calls, puts, zerodte, retail }
 * where `total == calls + puts` and (on this 0DTE terminal) `zerodte == total`,
 * so `zerodte` is redundant and not plotted. `total` is the HIRO line: positive
 * = net dealer BUYING pressure, negative = net SELLING; it walks across zero
 * through the session. `calls` / `puts` decompose it; `retail` is the retail
 * subset of the same flow.
 *
 * This module turns the frame list into epoch-second time-series (the shape
 * lightweight-charts wants) plus a latest-frame metrics readout. Pure + no DOM
 * (unit-tested with node:test), so it composes the same way as levelsChart.ts.
 */

export interface FluxBlock {
  total: number;
  calls: number;
  puts: number;
  zerodte: number;
  retail: number;
}

export interface FluxFrameLike {
  ts: string;
  flux: FluxBlock | null;
}

/** One time-series point: UTC epoch seconds + value (USD notional). */
export interface FluxPoint {
  time: number;
  value: number;
}

/** The four plottable series (each a per-minute cumulative line). */
export interface FluxSeries {
  total: FluxPoint[]; // HIRO line (calls + puts)
  calls: FluxPoint[];
  puts: FluxPoint[];
  retail: FluxPoint[];
}

export interface FluxMetrics {
  total: number | null; // latest cumulative net flow (USD)
  calls: number | null;
  puts: number | null;
  retail: number | null;
  retailShare: number | null; // 0..100 (|retail| / |total|)
  pcRatio: number | null; // |puts / calls|
}

export interface FluxModel {
  series: FluxSeries;
  metrics: FluxMetrics;
}

const EMPTY: FluxModel = {
  series: { total: [], calls: [], puts: [], retail: [] },
  metrics: { total: null, calls: null, puts: null, retail: null, retailShare: null, pcRatio: null },
};

function epochSeconds(ts: string): number | null {
  const ms = Date.parse(ts);
  return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
}

/**
 * Build the four cumulative time-series. Frames without a `flux` block are
 * skipped (honest gap, no interpolation); duplicate timestamps keep the first.
 */
export function buildFluxSeries(frames: FluxFrameLike[]): FluxSeries {
  const total: FluxPoint[] = [];
  const calls: FluxPoint[] = [];
  const puts: FluxPoint[] = [];
  const retail: FluxPoint[] = [];
  const seen = new Set<number>();
  for (const f of frames) {
    if (!f.flux) continue;
    const time = epochSeconds(f.ts);
    if (time == null || seen.has(time)) continue;
    const x = f.flux;
    if (![x.total, x.calls, x.puts, x.retail].every((v) => Number.isFinite(v))) continue;
    seen.add(time);
    total.push({ time, value: x.total });
    calls.push({ time, value: x.calls });
    puts.push({ time, value: x.puts });
    retail.push({ time, value: x.retail });
  }
  // Stream order is chronological, but sort defensively.
  const byTime = (a: FluxPoint, b: FluxPoint) => a.time - b.time;
  return {
    total: total.sort(byTime),
    calls: calls.sort(byTime),
    puts: puts.sort(byTime),
    retail: retail.sort(byTime),
  };
}

/** Latest-frame flux readout (the metrics strip). */
export function buildFluxMetrics(frames: FluxFrameLike[]): FluxMetrics {
  // Most recent frame that actually carries a flux block.
  let last: FluxBlock | null = null;
  for (let i = frames.length - 1; i >= 0; i--) {
    if (frames[i].flux) {
      last = frames[i].flux;
      break;
    }
  }
  if (!last) return EMPTY.metrics;
  const absTotal = Math.abs(last.total);
  return {
    total: last.total,
    calls: last.calls,
    puts: last.puts,
    retail: last.retail,
    retailShare: absTotal > 0 ? (Math.abs(last.retail) / absTotal) * 100 : null,
    pcRatio: last.calls !== 0 ? Math.abs(last.puts / last.calls) : null,
  };
}

/** Build the full Flux model (series + metrics). */
export function buildFluxModel(frames: FluxFrameLike[]): FluxModel {
  if (frames.length === 0) return EMPTY;
  return {
    series: buildFluxSeries(frames),
    metrics: buildFluxMetrics(frames),
  };
}
