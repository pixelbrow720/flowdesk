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
  profile: { strike: number; net_gex: number }[];
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
  theta_decay?: { net_theta: number; theta_sign: number } | null;
  max_pain?: { strike: number | null } | null;
  vol_expansion?: { expansion: number | null } | null;
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
  // Experimental 0DTE lenses (mirrors engine Snapshot optional fields).
  // All optional because the engine emits them only when their flag is set.
  thetaDecay?: number | null;
  maxPain?: number | null;
  volExpansion?: number | null;
}

/** One per-frame ratio time-series point (epoch seconds + value). */
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
  metrics: {
    atmVol: null,
    expectedMove: null,
    netGamma: null,
    gexLongShare: null,
    skew: null,
    thetaDecay: null,
    maxPain: null,
    volExpansion: null,
  },
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
 * EARLIEST non-null value of `pick` across frames. Used for the STATIC,
 * OI-based levels (call/put wall, the proprietary OI levels): open interest is
 * the prior session's settle (fixed all day), so these are frozen at the RTH
 * open and must NOT drift as the playhead advances. Scanning from frame 0 means
 * the value is the RTH-open reading and stays identical at every playhead.
 */
function firstNonNull(
  frames: LevelsFrameLike[],
  pick: (f: LevelsFrameLike) => number | null | undefined,
): number | null {
  for (let i = 0; i < frames.length; i++) {
    const v = pick(frames[i]);
    if (v != null && Number.isFinite(v)) return v;
  }
  return null;
}

/**
 * Gamma flip / Zero gamma — the price where PER-STRIKE net_gex transitions
 * between the positive-gamma zone and the negative-gamma zone. This is the
 * boundary the strike bars visibly flip color across, NOT the engine's
 * cumulative-sum crossing (`levels.gamma_flip`), which sits elsewhere and is
 * unstable. Computed from ONE frame's profile so it tracks the playhead.
 *
 * Finds sign changes of net_gex between adjacent strikes (ascending) and
 * linearly interpolates the zero. With several crossings, returns the one
 * nearest the forward. `null` when the profile never changes sign.
 */
export function perStrikeGammaFlip(
  profile: { strike: number; net_gex: number }[],
  forward?: number | null,
): number | null {
  const rows = profile
    .filter((p) => Number.isFinite(p.strike) && Number.isFinite(p.net_gex))
    .slice()
    .sort((a, b) => a.strike - b.strike);
  if (rows.length < 2) return null;

  const candidates: number[] = [];
  for (let i = 1; i < rows.length; i++) {
    const a = rows[i - 1].net_gex;
    const b = rows[i].net_gex;
    if ((a < 0 && b > 0) || (a > 0 && b < 0)) {
      const x0 = rows[i - 1].strike;
      const x1 = rows[i].strike;
      candidates.push(x0 + ((x1 - x0) * (0 - a)) / (b - a));
    } else if (a === 0) {
      candidates.push(rows[i - 1].strike);
    }
  }
  if (rows[rows.length - 1].net_gex === 0) {
    candidates.push(rows[rows.length - 1].strike);
  }
  if (candidates.length === 0) return null;
  if (forward != null && Number.isFinite(forward)) {
    return candidates.reduce((best, x) =>
      Math.abs(x - forward) < Math.abs(best - forward) ? x : best,
    );
  }
  return candidates[0];
}

/**
 * Resolve every key level for the CURRENT playhead and return the ones that
 * exist, each with display metadata.
 *
 * Two classes, deliberately different:
 *   - STATIC (OI-based): call/put wall + the proprietary OI levels are frozen
 *     at the RTH open (`firstNonNull`) — OI is the prior settle, fixed all day,
 *     so these lines must not wander as the session plays.
 *   - DYNAMIC (VOL-based): Zero γ (per-strike flip), largest GEX/DEX read the
 *     CURRENT (playhead) frame so they track the replay minute, not a stale
 *     last-known value.
 */
export function resolveKeyLevels(frames: LevelsFrameLike[]): KeyLevel[] {
  if (frames.length === 0) return [];
  const cur = frames[frames.length - 1]; // playhead frame
  const out: KeyLevel[] = [];
  const push = (
    id: string,
    label: string,
    color: string,
    experimental: boolean,
    price: number | null | undefined,
  ) => {
    if (price != null && Number.isFinite(price)) out.push({ id, label, price, color, experimental });
  };

  // STATIC (frozen at RTH open) ------------------------------------------- //
  push("call_wall", "Call Wall", "#0FB5A8", false, firstNonNull(frames, (f) => f.levels.call_walls?.[0]));
  push("put_wall", "Put Wall", "#B5002E", false, firstNonNull(frames, (f) => f.levels.put_walls?.[0]));

  // DYNAMIC (current playhead frame) -------------------------------------- //
  push("gamma_flip", "Zero γ", "#F59E0B", false, perStrikeGammaFlip(cur.profile, cur.forward));
  push("largest_gex", "Largest GEX", "#5BA3D0", false, cur.levels.largest_gex);
  push("largest_dex", "Largest DEX", "#8E8E88", false, cur.levels.largest_dex);

  // STATIC proprietary (OI-based, frozen) — EXPERIMENTAL ------------------ //
  push("hedge_wall", "Hedge Wall", "#D54452", true, firstNonNull(frames, (f) => f.proprietary?.hedge_wall));
  push("abs_gamma", "Abs γ Strike", "#6B655B", true, firstNonNull(frames, (f) => f.proprietary?.abs_gamma_strike));
  push("oi_gamma_flip", "OI γ Flip", "#8E8E88", true, firstNonNull(frames, (f) => f.proprietary?.oi_gamma_flip));

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
    thetaDecay: latestNonNull(frames, (f) => f.theta_decay?.net_theta),
    maxPain: latestNonNull(frames, (f) => f.max_pain?.strike),
    volExpansion: latestNonNull(frames, (f) => f.vol_expansion?.expansion),
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
