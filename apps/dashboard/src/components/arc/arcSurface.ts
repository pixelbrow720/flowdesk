/**
 * Arc surface — pure helpers for the Arc 3D volatility surface.
 *
 * Builds a σ(K, t) surface from per-minute snapshot frames, where each frame
 * carries an SVI fit (svi_a/b/rho/m/sigma). The surface is a 2D grid: rows
 * are minute indices (0..389 for a full session), columns are strikes around
 * the forward (log-moneyness space). Each cell is the implied volatility
 * reconstructed from the SVI fit at that minute — `σ(k) = sqrt(w(k)/T)`,
 * where `w(k)` is SVI total variance and `T` is the year-fraction remaining
 * to 16:00 ET (0DTE settlement).
 *
 * Also provides axonometric 3D projection helpers (yaw/pitch/zoom) and a
 * color map for IV level (low → turquoise, mid → bone, high → crimson).
 *
 * Pure + deterministic. No DOM. Unit-testable with node:test.
 */

import { sviTotalVariance, type SviParams } from "../fog/strikeMath.ts";

export interface SnapshotLike {
  minute_index: number;
  forward: number;
  surface: SviParams | null;
}

export interface VolSurfaceGrid {
  /** Strike axis (log-moneyness k = ln(K / F_ref)). */
  strikes: number[];
  /** Reference forward (last frame's forward). */
  forwardRef: number;
  /** Grid[t][i] = σ at minute_index t, strike strikes[i]. null if no SVI fit. */
  grid: (number | null)[][];
  /** Minute index axis (0..max_minute_index). */
  minutes: number[];
}

/**
 * Year-fraction remaining to 16:00 ET for a given minute_index (0 = RTH open
 * 09:30 ET; 16:00 ET = minute_index 390). Matches the locked engine convention
 * `t_expiry_from_clock` for 0DTE (see services/engine/src/engine/snapshot.py).
 */
function tExpiryFromMinuteIndex(minuteIndex: number): number {
  const MINUTES_PER_YEAR = 60 * 24 * 365;
  const RTH_MINUTES = 390; // 09:30 → 16:00 ET
  const remaining = RTH_MINUTES - minuteIndex;
  return remaining / MINUTES_PER_YEAR;
}

/**
 * Build a volatility surface grid from snapshot frames. Each frame contributes
 * one row (minute_index), and the strike axis is derived from the last frame's
 * forward ± pctBand (default 3%, so ~K ∈ [F*0.97, F*1.03]). The grid is sparse:
 * grid[t][i] is null if the frame at minute_index t has no SVI fit, or if the
 * implied vol is non-positive (rare, degenerate SVI).
 *
 * Strike axis is in log-moneyness space (k = ln(K / F_ref)), evenly spaced.
 * Implied vol at each cell is `sqrt(w(k) / T)` where `T` is the per-frame
 * year-fraction to 16:00 ET (matches engine surface formula `svi_vol`).
 *
 * @param frames Snapshot frames (assumed chronological)
 * @param pctBand Half-width of strike axis as fraction of forward (default 0.03)
 * @param strikeCount Number of strikes to evaluate (default 50)
 * @param binMinutes Bin frames into N-minute buckets; each bucket picks the LAST
 *                    frame. Default 1 = no binning (per-minute). Use 5 to smooth
 *                    per-minute SVI jitter into a 5-minute cadence.
 */
export function buildVolSurface(
  frames: SnapshotLike[],
  pctBand: number = 0.03,
  strikeCount: number = 50,
  binMinutes: number = 1
): VolSurfaceGrid {
  if (frames.length === 0) {
    return { strikes: [], forwardRef: 0, grid: [], minutes: [] };
  }

  const lastFrame = frames[frames.length - 1];
  const forwardRef = lastFrame.forward;
  const kMin = Math.log(1 - pctBand);
  const kMax = Math.log(1 + pctBand);
  const kStep = (kMax - kMin) / (strikeCount - 1);
  const strikes = Array.from({ length: strikeCount }, (_, i) => kMin + i * kStep);

  // Bin frames: each bin picks the LAST frame (later overwrites earlier).
  // binKeys stores the canonical minute_index for each bin (the bin's start).
  const bins = new Map<number, SnapshotLike>();
  const binSize = Math.max(1, binMinutes);
  for (const f of frames) {
    const binKey = Math.floor(f.minute_index / binSize) * binSize;
    bins.set(binKey, f); // later frames overwrite → last-frame-wins
  }
  const minutes = Array.from(bins.keys()).sort((a, b) => a - b);
  const grid: (number | null)[][] = minutes.map(() => new Array(strikeCount).fill(null));

  for (let rowIdx = 0; rowIdx < minutes.length; rowIdx++) {
    const frame = bins.get(minutes[rowIdx])!;
    if (!frame.surface) continue;
    const T = tExpiryFromMinuteIndex(frame.minute_index);
    if (T <= 0) continue; // past settlement; skip
    for (let i = 0; i < strikeCount; i++) {
      const k = strikes[i];
      const w = sviTotalVariance(k, frame.surface);
      if (w > 0) {
        const iv = Math.sqrt(w / T);
        if (Number.isFinite(iv) && iv > 0) {
          grid[rowIdx][i] = iv;
        }
      }
    }
  }

  return { strikes, forwardRef, grid, minutes };
}

export interface Point3D {
  x: number;
  y: number;
  z: number;
}

export interface Point2D {
  x: number;
  y: number;
}

export interface CameraState {
  yaw: number; // radians, rotation around Y axis
  pitch: number; // radians, rotation around X axis
  zoom: number; // scale factor
  centerX: number;
  centerY: number;
}

/**
 * Project a 3D point to 2D screen coordinates using axonometric projection.
 * Yaw rotates around Y, pitch rotates around X. Zoom scales uniformly.
 */
export function project3D(point: Point3D, camera: CameraState): Point2D {
  const { yaw, pitch, zoom, centerX, centerY } = camera;
  const cosYaw = Math.cos(yaw);
  const sinYaw = Math.sin(yaw);
  const cosPitch = Math.cos(pitch);
  const sinPitch = Math.sin(pitch);

  // Rotate around Y axis (yaw)
  const x1 = point.x * cosYaw - point.z * sinYaw;
  const z1 = point.x * sinYaw + point.z * cosYaw;

  // Rotate around X axis (pitch)
  const y1 = point.y * cosPitch - z1 * sinPitch;
  const z2 = point.y * sinPitch + z1 * cosPitch;

  // Orthographic projection (discard z2, apply zoom + translation)
  return {
    x: centerX + x1 * zoom,
    y: centerY + y1 * zoom,
  };
}

/**
 * Map an IV value to a color (RGB) for rendering. Low IV → turquoise, mid → bone,
 * high IV → crimson. Uses a smooth interpolation in RGB space.
 */
export function colorMapIV(
  iv: number,
  ivMin: number,
  ivMax: number
): { r: number; g: number; b: number } {
  const t = Math.max(0, Math.min(1, (iv - ivMin) / (ivMax - ivMin)));

  // Turquoise: rgb(15, 181, 168)
  // Bone: rgb(250, 250, 247)
  // Crimson: rgb(181, 0, 46)
  let r: number, g: number, b: number;

  if (t < 0.5) {
    // Turquoise → Bone
    const s = t * 2;
    r = 15 + (250 - 15) * s;
    g = 181 + (250 - 181) * s;
    b = 168 + (247 - 168) * s;
  } else {
    // Bone → Crimson
    const s = (t - 0.5) * 2;
    r = 250 + (181 - 250) * s;
    g = 250 + (0 - 250) * s;
    b = 247 + (46 - 247) * s;
  }

  return { r: Math.round(r), g: Math.round(g), b: Math.round(b) };
}

/**
 * Compute the min/max IV values in a volatility surface grid (ignoring nulls).
 *
 * `hiPercentile` (default 1 = exact max) caps the reported max at the given
 * percentile of all non-null values. This matters for 0DTE: in the last minutes
 * the wing IV (`σ = sqrt(w / T)`) blows up as `T → 0`, and an un-clamped max
 * compresses the whole surface's color/height relief. Passing e.g. 0.95 reports
 * the 95th-percentile value as the max so a handful of late-session wing
 * outliers don't dominate the scale. The min is always the true minimum.
 */
export function surfaceIVRange(
  grid: (number | null)[][],
  hiPercentile: number = 1
): { min: number; max: number } {
  const vals: number[] = [];
  for (const row of grid) {
    for (const v of row) {
      if (v !== null) vals.push(v);
    }
  }
  if (vals.length === 0) {
    return { min: 0, max: 0 };
  }
  vals.sort((a, b) => a - b);
  const min = vals[0];
  let max: number;
  if (hiPercentile >= 1) {
    max = vals[vals.length - 1];
  } else {
    const p = Math.max(0, Math.min(1, hiPercentile));
    const idx = Math.min(vals.length - 1, Math.floor(p * (vals.length - 1)));
    max = vals[idx];
  }
  if (!isFinite(min) || !isFinite(max)) {
    return { min: 0, max: 0 };
  }
  return { min, max };
}
