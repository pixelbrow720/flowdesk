/**
 * arcHeatmap — pure helpers for the Arc left-panel gamma-density heatmap.
 *
 * Renders a top-down view of the engine's `fog.gamma` field: x-axis is the
 * forward price grid (`fog.price_grid`), y-axis is the SESSION minute index
 * (one row per frame in the session, time flows DOWN — most recent minute at
 * the bottom). Cell color is the gamma exposure at that (price, minute) point,
 * on a diverging scale (turquoise = long-gamma / stabilising, crimson =
 * short-gamma / destabilising, bone = near-zero). A thin playhead line marks
 * the current minute_index so the heatmap stays in sync with the 3D surface.
 *
 * Pure + deterministic. No DOM. Unit-testable with node:test.
 */

export interface HeatmapFrame {
  minute_index: number;
  fog: { price_grid: number[]; gamma: number[]; delta: number[] } | null;
}

export interface HeatmapGrid {
  /** Sorted ascending price axis (index points). */
  prices: number[];
  /** Sorted ascending minute axis (one entry per frame that contributed a row). */
  minutes: number[];
  /** grid[r][c] = gamma at minute_axis[r] and prices[c]; null if missing. */
  grid: (number | null)[][];
  /** Min/max gamma used for the diverging color scale. */
  range: { min: number; max: number };
}

/**
 * Build a 2D heatmap grid from session frames carrying the engine's `fog`
 * field. Rows are sorted ascending by minute_index; columns by price_grid.
 * A cell is `null` when that frame's fog was null or its price_grid length
 * differed from the canonical axis.
 *
 * Gamma is dollarized per 1% price move (same as the locked GEX). For visual
 * scale symmetry we use a DIVERGING range — `[-|max|, +|max|]` so zero sits
 * at the bone midpoint and turquoise/crimson read symmetrically.
 */
export function buildHeatmap(frames: HeatmapFrame[]): HeatmapGrid {
  // Pick the canonical price_grid from the first non-empty fog. Different
  // frames SHOULD share the same axis (engine-level invariant) but we tolerate
  // any drift by using the first observed axis and zero-padding mismatches.
  let prices: number[] = [];
  for (const f of frames) {
    if (f.fog && f.fog.price_grid.length > 0) {
      prices = [...f.fog.price_grid].sort((a, b) => a - b);
      break;
    }
  }
  if (prices.length === 0) {
    return { prices: [], minutes: [], grid: [], range: { min: 0, max: 0 } };
  }

  const priceIndex = new Map<number, number>();
  for (let i = 0; i < prices.length; i++) priceIndex.set(prices[i], i);

  // Collect rows in chronological order, dropping frames without fog.
  const rows: { minute: number; row: (number | null)[] }[] = [];
  let absMax = 0;
  for (const f of frames) {
    if (!f.fog || f.fog.price_grid.length === 0 || f.fog.gamma.length === 0) continue;
    const row: (number | null)[] = new Array(prices.length).fill(null);
    for (let i = 0; i < f.fog.gamma.length; i++) {
      const p = f.fog.price_grid[i];
      const g = f.fog.gamma[i];
      if (!Number.isFinite(g)) continue;
      const col = priceIndex.get(p);
      if (col === undefined) continue;
      row[col] = g;
      if (Math.abs(g) > absMax) absMax = Math.abs(g);
    }
    rows.push({ minute: f.minute_index, row });
  }
  rows.sort((a, b) => a.minute - b.minute);

  return {
    prices,
    minutes: rows.map((r) => r.minute),
    grid: rows.map((r) => r.row),
    range: { min: -absMax, max: absMax },
  };
}

/**
 * Map a gamma value (and the heatmap's range) to an RGB triple on the locked
 * diverging palette:
 *   -max      → crimson  (#B5002E)
 *    0        → bone     (#FAFAF7)
 *   +max      → turquoise (#0FB5A8)
 * Mid-points blend linearly. NaN/non-finite → bone (mid gray).
 */
export function gammaToColor(
  gamma: number | null,
  range: { min: number; max: number },
): { r: number; g: number; b: number } {
  if (gamma === null || !Number.isFinite(gamma)) {
    return { r: 250, g: 250, b: 247 }; // bone
  }
  const span = Math.max(1e-12, range.max - range.min);
  // Normalize to [0, 1] where 0.5 = zero (because range is symmetric).
  const t = Math.max(0, Math.min(1, (gamma - range.min) / span));

  // Turquoise: rgb(15, 181, 168); Bone: rgb(250, 250, 247); Crimson: rgb(181, 0, 46).
  if (t < 0.5) {
    const s = t * 2; // 0..1 from crimson to bone
    return {
      r: 181 + (250 - 181) * s,
      g: 0 + (250 - 0) * s,
      b: 46 + (247 - 46) * s,
    };
  }
  const s = (t - 0.5) * 2; // 0..1 from bone to turquoise
  return {
    r: 250 + (15 - 250) * s,
    g: 250 + (181 - 250) * s,
    b: 247 + (168 - 247) * s,
  };
}