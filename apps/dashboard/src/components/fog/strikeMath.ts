/**
 * strikeMath — pure, deterministic helpers behind the Fog three-panel terminal.
 *
 * Everything here is a pure function of the snapshot frames: identical frames
 * always produce identical output (mirrors the engine's `build_snapshot`
 * determinism ethos). The React layer only consumes these results, so the
 * number-crunching can be unit-tested without a DOM.
 *
 * One pass over the session builds, per strike, for BOTH metrics (GEX + DEX):
 *   - current (latest frame), session MIN / MAX, and the 5-min change.
 * The center "dynamics" panel can render either metric, so DEX carries the same
 * min/max/momentum as GEX (not just a current value). Per-metric session scales
 * normalize everything to [-1, 1] so bars, the min/max/current lines, and the
 * flow momentum all share one frame of reference.
 */

/** Minimal shape of one snapshot frame this module reads. */
export interface FrameLike {
  profile: {
    strike: number;
    net_gex: number;
    net_dex: number;
    interpolated: boolean;
  }[];
}

/**
 * Bin a frame's $5-spaced profile into $10-multiple buckets with an OVERLAPPING
 * ±$5 window (user spec 2026-06-17): each bucket B (a multiple of 10) sums the
 * strikes B-5, B, B+5. A $5 tick therefore contributes to BOTH neighbouring
 * buckets (e.g. 7395 feeds 7390 and 7400), which is what produces the soft
 * "gradient" cross-fade at bucket edges.
 *
 * Worked example from the spec: with 7385=-45M, 7390=-50M, 7395=+85M,
 *   bucket 7390 = 7385 + 7390 + 7395 = -45 -50 +85 = -10M (still net short,
 *   but a softer red than 7390 alone).
 *
 * Interpolated rows are kept (binning is a display aggregation, not a
 * positioning read) but a bucket is only emitted if at least one of its three
 * member strikes carried a NON-interpolated value, so we never invent a bucket
 * out of pure gap-fill. Pure + deterministic.
 */
export function binFramesToTens(frames: FrameLike[]): FrameLike[] {
  return frames.map((f) => {
    const byStrike = new Map<number, { gex: number; dex: number; real: boolean }>();
    for (const p of f.profile) {
      const e = byStrike.get(p.strike);
      if (e) {
        e.gex += p.net_gex;
        e.dex += p.net_dex;
        e.real = e.real || !p.interpolated;
      } else {
        byStrike.set(p.strike, { gex: p.net_gex, dex: p.net_dex, real: !p.interpolated });
      }
    }

    // Every $10 multiple spanned by the chain becomes a candidate bucket.
    const buckets = new Map<number, { gex: number; dex: number; real: boolean }>();
    for (const strike of byStrike.keys()) {
      const base = Math.round(strike / 10) * 10;
      for (const b of [base - 10, base, base + 10]) {
        // Bucket b owns strikes b-5, b, b+5; only fold `strike` into b if it
        // is one of those three (an exact ±5 / 0 member).
        if (Math.abs(strike - b) <= 5 && (strike - b) % 5 === 0) {
          const src = byStrike.get(strike)!;
          const acc = buckets.get(b);
          if (acc) {
            acc.gex += src.gex;
            acc.dex += src.dex;
            acc.real = acc.real || src.real;
          } else {
            buckets.set(b, { gex: src.gex, dex: src.dex, real: src.real });
          }
        }
      }
    }

    const profile = Array.from(buckets.entries())
      .filter(([, v]) => v.real) // drop pure gap-fill buckets
      .map(([strike, v]) => ({
        strike,
        net_gex: v.gex,
        net_dex: v.dex,
        interpolated: false,
      }));
    return { profile };
  });
}

/** One metric's per-strike series (normalized [-1,1] + raw USD-notional). */
export interface MetricSeries {
  current: number; // normalized [-1, 1]
  low: number; // normalized session min
  high: number; // normalized session max
  absCurrent: number; // raw
  absLow: number;
  absHigh: number;
  diff5m: number; // raw 5-min change
  diff30m: number;
  diff60m: number;
  diff5mNorm: number; // normalized [-1, 1] (flow momentum)
}

/** Per-strike data consumed by all three panels. */
export interface StrikeDatum {
  price: number;
  gex: MetricSeries;
  dex: MetricSeries;
}

export type MetricKey = "gex" | "dex";

export interface StrikeModel {
  strikes: StrikeDatum[]; // sorted descending by price (top = highest strike)
  gexMaxAbs: number;
  dexMaxAbs: number;
}

interface Accum {
  latest: number;
  low: number;
  high: number;
  history: number[];
}

function emptyAccum(v: number): Accum {
  return { latest: v, low: v, high: v, history: [v] };
}

function pushAccum(a: Accum, v: number): void {
  a.latest = v;
  a.low = Math.min(a.low, v);
  a.high = Math.max(a.high, v);
  a.history.push(v);
}

/**
 * Percentile (0..100) of `value` within an inclusive [low, high] range.
 * Degenerate (zero-width) ranges return 0. Values outside the range clamp.
 */
export function percentileInRange(
  value: number,
  low: number,
  high: number,
): number {
  const span = high - low;
  if (span <= 0) return 0;
  const pct = ((value - low) / span) * 100;
  return Math.max(0, Math.min(100, pct));
}

/** Mean of the normalized `current` values for a metric — the center "average"
 *  vertical reference line. Empty input → 0. */
export function meanCurrent(strikes: StrikeDatum[], metric: MetricKey): number {
  if (strikes.length === 0) return 0;
  let sum = 0;
  for (const s of strikes) sum += s[metric].current;
  return sum / strikes.length;
}

function buildSeries(a: Accum, maxAbs: number, diffMaxAbs: number): MetricSeries {
  const h = a.history;
  const at = (back: number) => h[Math.max(0, h.length - back)] ?? a.latest;
  const diff5m = a.latest - at(5);
  return {
    current: a.latest / maxAbs,
    low: a.low / maxAbs,
    high: a.high / maxAbs,
    absCurrent: a.latest,
    absLow: a.low,
    absHigh: a.high,
    diff5m,
    diff30m: a.latest - at(30),
    diff60m: a.latest - at(60),
    diff5mNorm: Math.max(-1, Math.min(1, diff5m / diffMaxAbs)),
  };
}

/**
 * Build the full strike model (GEX + DEX series) from session frames.
 * Non-interpolated strikes only. Frames are assumed chronological, so the last
 * write per strike is the current value.
 */
export function buildStrikeModel(frames: FrameLike[]): StrikeModel {
  const gex = new Map<number, Accum>();
  const dex = new Map<number, Accum>();

  for (const f of frames) {
    for (const p of f.profile) {
      if (p.interpolated) continue;
      const g = gex.get(p.strike);
      if (g) pushAccum(g, p.net_gex);
      else gex.set(p.strike, emptyAccum(p.net_gex));
      const d = dex.get(p.strike);
      if (d) pushAccum(d, p.net_dex);
      else dex.set(p.strike, emptyAccum(p.net_dex));
    }
  }

  // Per-metric session scales (start at 1 so empty input never divides by zero).
  let gexMaxAbs = 1;
  let gexDiffMax = 1;
  for (const a of gex.values()) {
    gexMaxAbs = Math.max(gexMaxAbs, Math.abs(a.latest), Math.abs(a.low), Math.abs(a.high));
    const h = a.history;
    gexDiffMax = Math.max(gexDiffMax, Math.abs(a.latest - (h[Math.max(0, h.length - 5)] ?? a.latest)));
  }
  let dexMaxAbs = 1;
  let dexDiffMax = 1;
  for (const a of dex.values()) {
    dexMaxAbs = Math.max(dexMaxAbs, Math.abs(a.latest), Math.abs(a.low), Math.abs(a.high));
    const h = a.history;
    dexDiffMax = Math.max(dexDiffMax, Math.abs(a.latest - (h[Math.max(0, h.length - 5)] ?? a.latest)));
  }

  const strikes: StrikeDatum[] = Array.from(gex.keys()).map((price) => ({
    price,
    gex: buildSeries(gex.get(price)!, gexMaxAbs, gexDiffMax),
    dex: buildSeries(dex.get(price)!, dexMaxAbs, dexDiffMax),
  }));

  strikes.sort((a, b) => b.price - a.price);
  return { strikes, gexMaxAbs, dexMaxAbs };
}

/** SVI raw total-variance parameters (engine `surface.svi_*`). */
export interface SviParams {
  svi_a: number;
  svi_b: number;
  svi_rho: number;
  svi_m: number;
  svi_sigma: number;
}

/**
 * SVI raw total variance w(k) for log-moneyness k = ln(strike / forward):
 *   w(k) = a + b · ( rho·(k - m) + sqrt((k - m)² + sigma²) )
 * Returns total variance (≥ 0 for a well-formed surface); the smile overlay
 * uses sqrt(w) shape, self-normalized across the visible strikes, so absolute
 * units don't matter — it's a relative shape cue, labelled EXPERIMENTAL.
 */
export function sviTotalVariance(k: number, p: SviParams): number {
  const d = k - p.svi_m;
  return p.svi_a + p.svi_b * (p.svi_rho * d + Math.sqrt(d * d + p.svi_sigma * p.svi_sigma));
}

/**
 * Build a self-normalized smile curve (0..1, 0 = lowest vol in view) for the
 * given strikes against a forward and SVI params. Returns null if the surface
 * is degenerate (non-positive variance) so the overlay can be skipped.
 */
export function buildSmile(
  strikes: { price: number }[],
  forward: number,
  p: SviParams,
): { price: number; norm: number }[] | null {
  if (forward <= 0 || strikes.length === 0) return null;
  const raw = strikes.map((s) => {
    const k = Math.log(s.price / forward);
    const w = sviTotalVariance(k, p);
    return { price: s.price, vol: w > 0 ? Math.sqrt(w) : 0 };
  });
  let lo = Infinity;
  let hi = -Infinity;
  for (const r of raw) {
    lo = Math.min(lo, r.vol);
    hi = Math.max(hi, r.vol);
  }
  const span = hi - lo;
  if (!(span > 0)) return null;
  return raw.map((r) => ({ price: r.price, norm: (r.vol - lo) / span }));
}
