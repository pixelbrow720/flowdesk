/**
 * Unit tests for the pure Arc surface helpers.
 * Runner: node:test. From apps/dashboard:
 *   node --test src/components/arc/arcSurface.test.ts
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildVolSurface,
  project3D,
  colorMapIV,
  surfaceIVRange,
  type SnapshotLike,
} from "./arcSurface.ts";

function frame(
  minute_index: number,
  forward: number,
  surface: { svi_a: number; svi_b: number; svi_rho: number; svi_m: number; svi_sigma: number } | null
): SnapshotLike {
  return { minute_index, forward, surface };
}

const SAMPLE_SVI = {
  svi_a: 0.04,
  svi_b: 0.2,
  svi_rho: -0.5,
  svi_m: 0,
  svi_sigma: 0.1,
};

test("buildVolSurface: empty frames -> empty grid", () => {
  const s = buildVolSurface([]);
  assert.equal(s.strikes.length, 0);
  assert.equal(s.grid.length, 0);
  assert.equal(s.forwardRef, 0);
});

test("buildVolSurface: single frame with SVI populates one row", () => {
  const s = buildVolSurface([frame(0, 7000, SAMPLE_SVI)]);
  assert.equal(s.forwardRef, 7000);
  assert.equal(s.strikes.length, 50);
  assert.equal(s.minutes.length, 1);
  assert.equal(s.grid.length, 1);
  // Find the strike axis index closest to k=0 (ATM). The axis is log-moneyness
  // (k = ln(K/F)), so k≈0 means K≈F=7000. With 50 evenly spaced points in
  // [ln(0.97), ln(1.03)], the nearest grid index has small k != 0 — the
  // expected vol must be computed at THAT k (not at exact k=0).
  const atmIdx = s.strikes.reduce(
    (best, k, i) => (Math.abs(k) < Math.abs(s.strikes[best]) ? i : best),
    0,
  );
  const atmVol = s.grid[0][atmIdx];
  assert.ok(atmVol !== null);
  // Expected = sqrt(sviTotalVariance(k_atm, sample) / T_minute_0).
  // minute_index 0 -> 390 minutes to 16:00 ET -> T = 390 / (60 * 24 * 365)
  const T = 390 / (60 * 24 * 365);
  // Compute expected via the same SVI helper the production code uses, so the
  // test stays in sync if the SVI formula ever changes.
  const k = s.strikes[atmIdx];
  const d = k - SAMPLE_SVI.svi_m;
  const w =
    SAMPLE_SVI.svi_a +
    SAMPLE_SVI.svi_b *
      (SAMPLE_SVI.svi_rho * d + Math.sqrt(d * d + SAMPLE_SVI.svi_sigma ** 2));
  const expected = Math.sqrt(w / T);
  assert.ok(Math.abs(atmVol! - expected) < 1e-6);
});

test("buildVolSurface: null SVI frames leave nulls (no fabrication)", () => {
  const s = buildVolSurface([
    frame(0, 7000, SAMPLE_SVI),
    frame(1, 7000, null), // missing SVI
    frame(2, 7000, SAMPLE_SVI),
  ]);
  const atmIdx = s.strikes.reduce(
    (best, k, i) => (Math.abs(k) < Math.abs(s.strikes[best]) ? i : best),
    0,
  );
  assert.ok(s.grid[0][atmIdx] !== null);
  assert.equal(s.grid[1][atmIdx], null); // frame 1 has no SVI
  assert.ok(s.grid[2][atmIdx] !== null);
});

test("buildVolSurface: strike axis is log-moneyness space", () => {
  const s = buildVolSurface([frame(0, 10000, SAMPLE_SVI)], 0.05, 11);
  assert.equal(s.strikes.length, 11);
  // kMin = ln(0.95) ~ -0.0513, kMax = ln(1.05) ~ +0.0488 (asymmetric on purpose:
  // ln(F*(1-p)) != -ln(F*(1+p)); verified mathematically).
  assert.ok(s.strikes[0] < 0);
  assert.ok(s.strikes[10] > 0);
  // Step is uniform: |strikes[i+1] - strikes[i]| is constant.
  const step = s.strikes[1] - s.strikes[0];
  for (let i = 1; i < s.strikes.length; i++) {
    assert.ok(Math.abs(s.strikes[i] - s.strikes[i - 1] - step) < 1e-12);
  }
});

test("project3D: yaw=0, pitch=0 maps (x,y,z) to (x,y) in screen space", () => {
  const cam = { yaw: 0, pitch: 0, zoom: 1, centerX: 0, centerY: 0 };
  const p = project3D({ x: 5, y: 3, z: 7 }, cam);
  assert.equal(p.x, 5);
  assert.equal(p.y, 3);
});

test("project3D: zoom scales uniformly", () => {
  const cam = { yaw: 0, pitch: 0, zoom: 2, centerX: 0, centerY: 0 };
  const p = project3D({ x: 5, y: 3, z: 7 }, cam);
  assert.equal(p.x, 10);
  assert.equal(p.y, 6);
});

test("project3D: yaw=π/2 rotates x-z plane (x becomes -z, z becomes x)", () => {
  const cam = { yaw: Math.PI / 2, pitch: 0, zoom: 1, centerX: 0, centerY: 0 };
  const p = project3D({ x: 5, y: 3, z: 0 }, cam);
  // x1 = 5*cos(π/2) - 0*sin(π/2) = 0
  assert.ok(Math.abs(p.x) < 1e-9);
  assert.equal(p.y, 3);
});

test("colorMapIV: low value → turquoise", () => {
  const c = colorMapIV(0.1, 0.1, 0.5);
  assert.equal(c.r, 15);
  assert.equal(c.g, 181);
  assert.equal(c.b, 168);
});

test("colorMapIV: high value → crimson", () => {
  const c = colorMapIV(0.5, 0.1, 0.5);
  assert.equal(c.r, 181);
  assert.equal(c.g, 0);
  assert.equal(c.b, 46);
});

test("colorMapIV: mid value → bone", () => {
  const c = colorMapIV(0.3, 0.1, 0.5);
  assert.equal(c.r, 250);
  assert.equal(c.g, 250);
  assert.equal(c.b, 247);
});

test("colorMapIV: clamps out-of-range values", () => {
  const low = colorMapIV(-1, 0.1, 0.5);
  const high = colorMapIV(2, 0.1, 0.5);
  assert.deepEqual(low, colorMapIV(0.1, 0.1, 0.5));
  assert.deepEqual(high, colorMapIV(0.5, 0.1, 0.5));
});

test("surfaceIVRange: ignores nulls and finds true min/max", () => {
  const grid = [
    [0.1, null, 0.5],
    [null, 0.3, null],
    [0.4, 0.2, 0.6],
  ];
  const r = surfaceIVRange(grid);
  assert.equal(r.min, 0.1);
  assert.equal(r.max, 0.6);
});

test("surfaceIVRange: all-null grid → zero range (safe)", () => {
  const r = surfaceIVRange([
    [null, null],
    [null, null],
  ]);
  assert.equal(r.min, 0);
  assert.equal(r.max, 0);
});

test("surfaceIVRange: default reports exact max (no clamp)", () => {
  // 0DTE wing outlier: one huge value among small ones. Default must keep it.
  const grid = [[0.2, 0.3, 0.25, 0.28, 5.0]];
  const r = surfaceIVRange(grid);
  assert.equal(r.min, 0.2);
  assert.equal(r.max, 5.0);
});

test("surfaceIVRange: hiPercentile caps the max below outliers", () => {
  // 10 values 0.1..1.0; the 1.0 is the outlier. 90th percentile → idx
  // floor(0.9 * 9) = 8 → 0.9, so the 1.0 spike is excluded from the scale.
  const grid = [[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]];
  const r = surfaceIVRange(grid, 0.9);
  assert.equal(r.min, 0.1);
  assert.equal(r.max, 0.9);
});
