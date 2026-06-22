/**
 * arcHeatmap — pure helpers for the Arc left-panel gamma-density TABLE.
 *
 * The left panel of the Arc section: a strike × minute table where each cell
 * shows the gamma exposure at that (price, time) point. Rows are minute_index
 * (newest at the bottom), columns are the forward price grid. Cell BACKGROUND
 * uses the diverging palette (crimson short-gamma → bone zero → turquoise
 * long-gamma) and cell TEXT shows the gamma value in compact form. Pure +
 * deterministic, used by both the table renderer and the existing tests.
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
 * Build a 2D grid from session frames carrying the engine's `fog` field.
 * Rows are sorted ascending by minute_index; columns by price_grid. A cell
 * is `null` when that frame's fog was null or its price_grid length differed
 * from the canonical axis.
 *
 * Gamma is dollarized per 1% price move (same as the locked GEX). The range
 * is symmetric (`[-|max|, +|max|]`) so zero sits at the bone midpoint and
 * turquoise/crimson read symmetrically in the table cell backgrounds.
 */
export function buildHeatmap(frames: HeatmapFrame[]): HeatmapGrid {
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
 * Mid-points blend linearly. NaN/non-finite → bone (mid).
 */
export function gammaToColor(
  gamma: number | null,
  range: { min: number; max: number },
): { r: number; g: number; b: number } {
  if (gamma === null || !Number.isFinite(gamma)) {
    return { r: 250, g: 250, b: 247 };
  }
  const span = Math.max(1e-12, range.max - range.min);
  const t = Math.max(0, Math.min(1, (gamma - range.min) / span));
  if (t < 0.5) {
    const s = t * 2;
    return {
      r: 181 + (250 - 181) * s,
      g: 0 + (250 - 0) * s,
      b: 46 + (247 - 46) * s,
    };
  }
  const s = (t - 0.5) * 2;
  return {
    r: 250 + (15 - 250) * s,
    g: 250 + (181 - 250) * s,
    b: 247 + (168 - 247) * s,
  };
}

/**
 * Compact gamma formatter: "$12.3M" / "-456K" / "$78.9B". Returns "—" for
 * null/NaN so the table cell renders a placeholder instead of "NaN".
 */
export function formatGamma(g: number | null): string {
  if (g === null || !Number.isFinite(g)) return "—";
  const abs = Math.abs(g);
  const sign = g < 0 ? "-" : "";
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(1)}K`;
  return `${sign}${abs.toFixed(0)}`;
}

/**
 * Choose how often to sample minutes so the table stays readable. Returns
 * the minute indices to show as rows: a uniform sample of the array capped
 * at `maxRows` (defaults to <= maxRows entries; the first and last frames are
 * always included as anchors).
 */
export function sampleRows(minutes: number[], maxRows: number): number[] {
  if (minutes.length === 0) return [];
  if (minutes.length <= maxRows) return minutes;
  const step = Math.max(1, Math.ceil(minutes.length / maxRows));
  const out: number[] = [];
  for (let i = 0; i < minutes.length; i += step) out.push(minutes[i]);
  // Anchor: always include the last frame if it's not already the last entry.
  const lastIdx = minutes.length - 1;
  if (out[out.length - 1] !== minutes[lastIdx]) out.push(minutes[lastIdx]);
  // Cap to maxRows (drop the second-to-last if we overflowed).
  while (out.length > maxRows) out.splice(out.length - 2, 1);
  return out;
}