/**
 * Shared vertical price/strike scale.
 *
 * The locked layout (PRD #4) puts a SINGLE centered strike axis between the
 * left profile line and the right heatmap, with both panels sharing the same
 * Y mapping so their rows align exactly. This module is that single source of
 * truth: strike (index points) -> vertical pixel position.
 *
 * Convention (matches the 4.2 heatmap, which flips Y so higher strike is at the
 * top): strike_max -> y = 0 (top), strike_min -> y = height (bottom). The scale
 * is purely linear over [strike_min, strike_max].
 */

export interface YScale {
  /** Domain low (index points). */
  readonly strikeMin: number;
  /** Domain high (index points). */
  readonly strikeMax: number;
  /** Strike increment (/ES = 5, /NQ = 10). */
  readonly step: number;
  /** Pixel height of the plotting area. */
  readonly height: number;
  /** Map a strike -> y pixel (0 = top = strikeMax). */
  yOf: (strike: number) => number;
  /** Inverse: y pixel -> strike. */
  strikeOf: (y: number) => number;
  /** Strike tick values, ascending, every `step`. */
  ticks: () => number[];
}

/** Build a linear Y scale for the given axis bounds and pixel height. */
export function makeYScale(
  strikeMin: number,
  strikeMax: number,
  step: number,
  height: number,
): YScale {
  const span = strikeMax - strikeMin || 1;
  const yOf = (strike: number) => {
    const t = (strike - strikeMin) / span; // 0 at min, 1 at max
    return height * (1 - t); // flip: max at top
  };
  const strikeOf = (y: number) => {
    const t = 1 - y / (height || 1);
    return strikeMin + t * span;
  };
  const ticks = () => {
    const out: number[] = [];
    for (let s = strikeMin; s <= strikeMax + 1e-9; s += step) {
      out.push(Math.round(s * 1e6) / 1e6);
    }
    return out;
  };
  return { strikeMin, strikeMax, step, height, yOf, strikeOf, ticks };
}

/**
 * Build a Y scale WINDOWED to +/- `windowPts` points around `center` (the
 * zero-gamma / gamma-flip level, falling back to the forward when flip is null).
 * Bounds are snapped to the `step` grid so ticks land on real strikes. Used to
 * focus both panels on the money (PRD: ~50 points each side of zero gamma).
 */
export function makeWindowedYScale(
  center: number,
  windowPts: number,
  step: number,
  height: number,
): YScale {
  const lo = Math.floor((center - windowPts) / step) * step;
  const hi = Math.ceil((center + windowPts) / step) * step;
  return makeYScale(lo, hi, step, height);
}
