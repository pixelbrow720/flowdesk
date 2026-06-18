/**
 * levelsChart — pure helpers for the Fog right panel (price chart + key levels).
 *
 * Builds, from the session frames:
 *   - candles : 1-min OHLC from the forward series (engine `ohlc` is null, so
 *               open = previous close, close = this minute, high/low = max/min;
 *               a standard close-series candle, no fabricated intrabar range).
 *   - levels  : the LATEST resolvable value of each key level. Many levels go
 *               null on the final minute, so each resolves to the most recent
 *               non-null reading (honest "last known", not interpolated).
 *   - metrics : latest session metrics for the overlay strip (ATM IV, expected
 *               move, net gamma, GEX+ share, skew) — all straight from data.
 *
 * Pure + deterministic. No DOM. EXPERIMENTAL levels/metrics are flagged so the
 * panel can label them; none are price-validated (AGENTS.md gap #1).
 */

export interface LevelsFrameLike {
  ts: string;
  forward: number;
  profile: { net_gex: number }[];
  regime: { net_gamma: number };
  levels: {
    call_walls: number[];
    put_walls: number[];
    gamma_flip: number | null;
    largest_gex: number | null;
    largest_dex: number | null;
  };
  surface: {
    atm_vol: number;
    expected_move: number;
    skew: number;
  } | null;
  proprietary: {
    oi_gamma_flip: number | null;
    abs_gamma_strike: number | null;
    hedge_wall: number | null;
  } | null;
}

/** One candlestick: UTC epoch seconds + OHLC. */
export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

/** A togglable key-level: id, label, price, color token, experimental flag. */
export interface KeyLevel {
  id: string;
  label: string;
  price: number;
  color: string;
  experimental: boolean;
}

export interface SessionMetrics {
  atmVol: number | null; // fraction (e.g. 0.20 = 20%)
  expectedMove: number | null; // index points (±)
  netGamma: number | null; // USD per 1% move
  gexLongShare: number | null; // 0..100 (% of |GEX| that is positive)
  skew: number | null; // SVI slope (negative = put skew)
}

/** One point of a per-frame ratio time-series (epoch seconds + value). */
export interface RatioPoint {
  time: number;
  value: number;
}

/** Per-frame ratio overlays the chart can draw as toggleable lines. */
export interface RatioSeries {
  gexLongShare: RatioPoint[]; // 0..100 (% of |GEX| that is long)
  atmVol: RatioPoint[]; // %  (0.20 → 20)
  skew: RatioPoint[]; // SVI slope (negative = put skew)
}

export interface LevelsChartModel {
  candles: Candle[];
  levels: KeyLevel[];
  metrics: SessionMetrics;
  ratios: RatioSeries;
}

const EMPTY: LevelsChartModel = {
  candles: [],
  levels: [],
  metrics: { atmVol: null, expectedMove: null, netGamma: null, gexLongShare: null, skew: null },
  ratios: { gexLongShare: [], atmVol: [], skew: [] },
};

function epochSeconds(ts: string): number | null {
  const ms = Date.parse(ts);
  return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
}

/** Build 1-min OHLC candles from the per-minute forward series. */
export function buildCandles(frames: LevelsFrameLike[]): Candle[] {
  const pts: { time: number; value: number }[] = [];
  const seen = new Set<number>();
  for (const f of frames) {
    const time = epochSeconds(f.ts);
    if (time == null || !Number.isFinite(f.forward)) continue;
    if (seen.has(time)) continue;
    seen.add(time);
    pts.push({ time, value: f.forward });
  }
  pts.sort((a, b) => a.time - b.time);
  return pts.map((p, i) => {
    const open = i > 0 ? pts[i - 1].value : p.value;
    const close = p.value;
    return {
      time: p.time,
      open: +open.toFixed(2),
      high: +Math.max(open, close).toFixed(2),
      low: +Math.min(open, close).toFixed(2),
      close: +close.toFixed(2),
    };
  });
}

/** Most-recent non-null value of `pick` across frames (chronological order). */
function latestNonNull(
  frames: LevelsFrameLike[],
  pick: (f: LevelsFrameLike) => number | null | undefined,
): number | null {
  for (let i = frames.length - 1; i >= 0; i--) {
    const v = pick(frames[i]);
    if (v != null && Number.isFinite(v)) return v;
  }
  return null;
}

/**
 * Resolve every key level to its latest non-null reading and return the ones
 * that exist, each with its display metadata. Walls take the top (rank-0) value.
 */
export function resolveKeyLevels(frames: LevelsFrameLike[]): KeyLevel[] {
  if (frames.length === 0) return [];
  const defs: { id: string; label: string; color: string; experimental: boolean; pick: (f: LevelsFrameLike) => number | null | undefined }[] = [
    { id: "call_wall", label: "Call Wall", color: "#0FB5A8", experimental: false, pick: (f) => f.levels.call_walls?.[0] },
    { id: "put_wall", label: "Put Wall", color: "#B5002E", experimental: false, pick: (f) => f.levels.put_walls?.[0] },
    { id: "gamma_flip", label: "Zero γ", color: "#F59E0B", experimental: false, pick: (f) => f.levels.gamma_flip },
    { id: "largest_gex", label: "Largest GEX", color: "#5BA3D0", experimental: false, pick: (f) => f.levels.largest_gex },
    { id: "largest_dex", label: "Largest DEX", color: "#8E8E88", experimental: false, pick: (f) => f.levels.largest_dex },
    { id: "hedge_wall", label: "Hedge Wall", color: "#D54452", experimental: true, pick: (f) => f.proprietary?.hedge_wall },
    { id: "abs_gamma", label: "Abs γ Strike", color: "#6B655B", experimental: true, pick: (f) => f.proprietary?.abs_gamma_strike },
    { id: "oi_gamma_flip", label: "OI γ Flip", color: "#8E8E88", experimental: true, pick: (f) => f.proprietary?.oi_gamma_flip },
  ];
  const out: KeyLevel[] = [];
  for (const d of defs) {
    const price = latestNonNull(frames, d.pick);
    if (price != null) out.push({ id: d.id, label: d.label, price, color: d.color, experimental: d.experimental });
  }
  return out;
}

/** GEX long-share (0..100): % of total |net_gex| that is positive. Null if flat. */
function gexLongShareOf(frame: LevelsFrameLike): number | null {
  let pos = 0;
  let abs = 0;
  for (const p of frame.profile) {
    const v = p.net_gex;
    if (!Number.isFinite(v)) continue;
    if (v > 0) pos += v;
    abs += Math.abs(v);
  }
  return abs > 0 ? (pos / abs) * 100 : null;
}

/** Build the latest-frame metrics strip. */
export function buildMetrics(frames: LevelsFrameLike[]): SessionMetrics {
  if (frames.length === 0) return EMPTY.metrics;
  const last = frames[frames.length - 1];
  return {
    atmVol: latestNonNull(frames, (f) => f.surface?.atm_vol),
    expectedMove: latestNonNull(frames, (f) => f.surface?.expected_move),
    netGamma: Number.isFinite(last.regime?.net_gamma) ? last.regime.net_gamma : null,
    gexLongShare: gexLongShareOf(last),
    skew: latestNonNull(frames, (f) => f.surface?.skew),
  };
}

/**
 * Build per-frame ratio time-series for the toggleable chart overlays. Each
 * point is emitted only where its source value exists (no interpolation), so
 * the surface-derived lines have honest gaps on frames missing a surface fit.
 */
export function buildRatios(frames: LevelsFrameLike[]): RatioSeries {
  const gexLongShare: RatioPoint[] = [];
  const atmVol: RatioPoint[] = [];
  const skew: RatioPoint[] = [];
  for (const f of frames) {
    const time = epochSeconds(f.ts);
    if (time == null) continue;
    const share = gexLongShareOf(f);
    if (share != null) gexLongShare.push({ time, value: share });
    if (f.surface) {
      if (Number.isFinite(f.surface.atm_vol)) atmVol.push({ time, value: f.surface.atm_vol * 100 });
      if (Number.isFinite(f.surface.skew)) skew.push({ time, value: f.surface.skew });
    }
  }
  return { gexLongShare, atmVol, skew };
}

/** Build the full model (candles + levels + metrics + ratio overlays). */
export function buildLevelsChart(frames: LevelsFrameLike[]): LevelsChartModel {
  if (frames.length === 0) return EMPTY;
  return {
    candles: buildCandles(frames),
    levels: resolveKeyLevels(frames),
    metrics: buildMetrics(frames),
    ratios: buildRatios(frames),
  };
}
