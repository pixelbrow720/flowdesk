/**
 * 2D field builder for the heatmap (time x price).
 *
 * The Snapshot `field` is 1D (one value per price-grid node for the current
 * minute). The heatmap renders a 2D field: X = intraday time (minutes), Y =
 * price/strike. In LIVE use the worker appends one column per minute; for
 * offline dev we synthesize a plausible evolving sequence from the single mock
 * snapshot so the centerpiece has something to render with no backend.
 *
 * Values are normalized SYMMETRICALLY around zero to [0,1] for the shader:
 *   0.0 = strongest positive (turquoise), 0.5 = neutral, 1.0 = strongest
 *   negative (crimson). Normalization uses the max ABS magnitude so the neutral
 *   midpoint always lands on the mid ramp anchor.
 */

export type Basis = "GAMMA" | "DELTA";

export interface Field2D {
  /** Column count (time/minutes). */
  width: number;
  /** Row count (price-grid nodes). */
  height: number;
  /** Row-major, length width*height, each in [0,1] (shader convention). */
  data: Float32Array;
  /** The price grid (Y axis), low->high index points. */
  priceGrid: number[];
  /** Max abs magnitude used for normalization (for the colorbar legend). */
  maxAbs: number;
  /** X in [0,1] of the flashlight source (the latest candle / right edge). */
  focusX: number;
}

/** Normalize a signed value to [0,1]: +max->0, 0->0.5, -max->1. */
function normalizeSigned(value: number, maxAbs: number): number {
  if (maxAbs <= 0) return 0.5;
  const t = 0.5 - 0.5 * (value / maxAbs);
  return Math.max(0, Math.min(1, t));
}

/**
 * Synthesize a `minutes`-wide 2D field from a 1D snapshot field array by
 * slowly drifting the profile over time (deterministic; no Math.random so SSR
 * and client agree). The newest column (right edge) equals the snapshot's
 * current 1D field exactly.
 */
export function buildMockField2D(
  field1d: number[],
  priceGrid: number[],
  minutes: number,
): Field2D {
  const height = field1d.length;
  const width = Math.max(1, minutes);
  const data = new Float32Array(width * height);

  // Max abs across the synthesized sequence (so coloring is stable over time).
  let maxAbs = 0;
  const cols: number[][] = [];
  for (let x = 0; x < width; x++) {
    // age 0 at the newest (rightmost) column, growing into the past.
    const age = (width - 1 - x) / width; // 0..~1
    const drift = 1 - 0.45 * age; // older minutes are muted
    const phase = Math.sin((age * Math.PI) / 2); // slow s-curve evolution
    const col: number[] = new Array(height);
    for (let y = 0; y < height; y++) {
      const base = field1d[y] ?? 0;
      // Shift the hump slightly with time to look like an evolving field.
      const neighbor = field1d[Math.min(height - 1, y + Math.round(phase * 2))] ?? base;
      const v = (base * (1 - 0.3 * phase) + neighbor * 0.3 * phase) * drift;
      col[y] = v;
      const a = Math.abs(v);
      if (a > maxAbs) maxAbs = a;
    }
    cols.push(col);
  }

  for (let x = 0; x < width; x++) {
    const col = cols[x];
    if (col === undefined) continue;
    for (let y = 0; y < height; y++) {
      // Texture row 0 = bottom. Flip Y so higher strike renders at the top.
      const row = height - 1 - y;
      data[row * width + x] = normalizeSigned(col[y] ?? 0, maxAbs);
    }
  }

  return { width, height, data, priceGrid, maxAbs, focusX: 1 };
}

/** Pick the basis array from a snapshot field. */
export function fieldArrayFor(
  field: { gamma: number[]; delta: number[] },
  basis: Basis,
): number[] {
  return basis === "GAMMA" ? field.gamma : field.delta;
}

/** One frame's data the heatmap consumes: the TRACE-style projected field. */
export interface ProfileFrame {
  profile: { strike: number; net_gex: number; net_dex: number }[];
  /** Re-evaluated exposure surface (engine.field): value per price_grid node. */
  field: { price_grid: number[]; gamma: number[]; delta: number[] };
}

/** Which signed field series feeds the heatmap (synced with the profile panel). */
export type HeatMetric = "net_gex" | "net_dex";

/** Minutes of history shown in the candle region before it slides. */
const WINDOW_MINUTES = 180; // 3 hours
/** Empty space kept on the RIGHT of the panel (fraction of total width). */
const RIGHT_MARGIN = 0.25;
/** Percentile used to clip the colour scale (anti-skew: a single 0DTE gamma
 *  spike must not burn the whole map to neutral). PRD/research §G. */
const CLIP_PERCENTILE = 0.98;

/** One visible candle's source frame-index range [start, end] (close = end). */
export type CandleBin = [number, number];

export interface CandleWindow {
  /** Visible candles oldest->newest, LEFT-aligned at columns [0, bins.length). */
  bins: CandleBin[];
  /** Total columns; candles fill the left ~75%, the right 25% stays empty. */
  totalCols: number;
}

/**
 * Fixed-width sliding candle window. Candle width is CONSTANT (never stretched
 * to fit): the first ~3 hours fill the candle region left->right; after that the
 * oldest candle drops and the newest enters from the front. 25% of the panel is
 * always kept empty on the right so the latest candle never touches the edge.
 */
export function candleWindow(
  framesLength: number,
  upToIndex: number,
  candleSize: number,
): CandleWindow {
  const last = Math.max(0, Math.min(upToIndex, framesLength - 1));
  const bin = Math.max(1, candleSize);
  const visible = Math.max(1, Math.ceil(WINDOW_MINUTES / bin));
  const totalCols = Math.max(1, Math.ceil(visible / (1 - RIGHT_MARGIN)));

  const all: CandleBin[] = [];
  for (let start = 0; start <= last; start += bin) {
    all.push([start, Math.min(start + bin - 1, last)]);
  }
  const bins = all.length <= visible ? all : all.slice(all.length - visible);
  return { bins, totalCols };
}

/** P-th percentile of |values| (clip scale). Empty -> 0. */
function percentileAbs(values: number[], p: number): number {
  if (values.length === 0) return 0;
  const arr = values.map((v) => Math.abs(v)).sort((a, b) => a - b);
  const idx = Math.min(arr.length - 1, Math.max(0, Math.floor(p * (arr.length - 1))));
  return arr[idx] ?? 0;
}

/**
 * Project one frame's 1D exposure field onto a shared target price grid.
 * Returns a column of length `targetGrid.length`. Missing frame / missing
 * field => all-zero column (caller treats as neutral).
 */
function projectFrameOntoGrid(
  frame: ProfileFrame | undefined,
  metric: HeatMetric,
  targetGrid: number[],
): number[] {
  const height = targetGrid.length;
  const col = new Array<number>(height).fill(0);
  if (!frame || !frame.field) return col;
  const series = metric === "net_gex" ? frame.field.gamma : frame.field.delta;
  const grid = frame.field.price_grid;
  if (!grid || !series || grid.length === 0) return col;
  const byPrice = new Map<number, number>();
  for (let i = 0; i < grid.length; i++) {
    const p = grid[i];
    if (p !== undefined) byPrice.set(p, series[i] ?? 0);
  }
  for (let y = 0; y < height; y++) {
    col[y] = byPrice.get(targetGrid[y] ?? -1) ?? 0;
  }
  return col;
}

/**
 * Build the 2D heatmap field from a sequence of replay frames, using the
 * engine's TRACE-style projected field (`field.gamma` / `field.delta`) — the
 * dealer exposure RE-EVALUATED at each hypothetical spot.
 *
 * - Columns use a FIXED-WIDTH sliding window (see {@link candleWindow}): candle
 *   width never changes, the right 25% stays empty.
 * - Each visible candle column shows the close-of-bin frame's projected field
 *   (true historical evolution along X); a missing frame degrades that column
 *   to neutral instead of crashing.
 * - Colour scale is clipped at the 98th percentile of |value| ACROSS ALL bins
 *   so the scale stays stable as the panel slides (a single 0DTE gamma spike
 *   can't compress the whole field to black — "senter" brightness convention).
 * - Values normalize symmetrically: +clip -> 0 (turquoise), 0 -> 0.5 (neutral),
 *   -clip -> 1 (crimson).
 */
export function buildReplayField2D(
  frames: ProfileFrame[],
  upToIndex: number,
  metric: HeatMetric,
  targetGrid: number[],
  candleSize: number,
): Field2D {
  const height = targetGrid.length;
  const { bins, totalCols } = candleWindow(frames.length, upToIndex, candleSize);
  const width = Math.max(1, totalCols);
  const data = new Float32Array(width * height);
  const last = Math.max(0, Math.min(upToIndex, frames.length - 1));
  const latest = frames[last];

  // Phase 1: project each visible bin's CLOSE-OF-BIN frame onto the shared
  // strike grid. cols[x] is the per-strike column for candle x. Collect all
  // non-zero magnitudes across every column so the clip percentile is computed
  // over the whole visible window (stable color scale as the panel slides).
  const cols: number[][] = [];
  const allMags: number[] = [];
  for (let x = 0; x < bins.length; x++) {
    const bin = bins[x];
    const closeIdx = bin ? bin[1] : last;
    // Fall back to the latest frame if the close-of-bin frame is missing.
    const binFrame = frames[closeIdx] ?? latest;
    const col = projectFrameOntoGrid(binFrame, metric, targetGrid);
    cols.push(col);
    for (let y = 0; y < height; y++) {
      const v = col[y] ?? 0;
      if (v !== 0) allMags.push(v);
    }
  }

  const clip = percentileAbs(allMags, CLIP_PERCENTILE) || 1;
  const candleCols = bins.length;

  // Phase 2: fill the texture. Candle region carries the per-bin field; the
  // right margin stays neutral (0.5 -> black so the flashlight has nothing to
  // light there).
  for (let y = 0; y < height; y++) {
    const row = height - 1 - y; // flip: higher strike at top
    for (let x = 0; x < width; x++) {
      if (x < candleCols) {
        const col = cols[x];
        const v = col?.[y] ?? 0;
        data[row * width + x] = normalizeSigned(v, clip);
      } else {
        data[row * width + x] = 0.5;
      }
    }
  }

  // Flashlight source = leading edge of the candle stream (the newest candle).
  const focusX = candleCols / width;
  return { width, height, data, priceGrid: targetGrid, maxAbs: clip, focusX };
}
