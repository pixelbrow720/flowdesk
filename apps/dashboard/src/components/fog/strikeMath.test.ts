/**
 * Unit tests for the pure Fog strike-math helpers.
 *
 * Runner: Node's built-in `node:test` (no extra deps). Node strips the TS types
 * natively. Run from apps/dashboard:
 *   node --test src/components/fog/strikeMath.test.ts
 *
 * These cover the determinism-critical bits the design calls out: the session
 * MIN/MAX (the turquoise/crimson lines), the percentile of "now", the
 * normalized 5-min momentum (flow), the mean reference line, and the
 * self-normalized SVI smile shape — for BOTH metrics (GEX + DEX).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildStrikeModel,
  binFramesToTens,
  percentileInRange,
  meanCurrent,
  sviTotalVariance,
  buildSmile,
  type FrameLike,
} from "./strikeMath.ts";

function frame(rows: [number, number, number][]): FrameLike {
  return {
    profile: rows.map(([strike, net_gex, net_dex]) => ({
      strike,
      net_gex,
      net_dex,
      interpolated: false,
    })),
  };
}

test("binFramesToTens: overlapping ±5 window matches the spec example", () => {
  // 7385=-45, 7390=-50, 7395=+85, 7400=+100, 7405=+30, 7410=+40 (gex == dex here).
  const frames = [
    frame([
      [7385, -45, -45],
      [7390, -50, -50],
      [7395, 85, 85],
      [7400, 100, 100],
      [7405, 30, 30],
      [7410, 40, 40],
    ]),
  ];
  const binned = binFramesToTens(frames);
  const byStrike = new Map(binned[0].profile.map((p) => [p.strike, p]));

  // Bucket 7390 = 7385 + 7390 + 7395 = -45 -50 +85 = -10 (still net short).
  assert.equal(byStrike.get(7390)!.net_gex, -10);
  // Bucket 7400 = 7395 + 7400 + 7405 = 85 + 100 + 30 = 215.
  assert.equal(byStrike.get(7400)!.net_gex, 215);
  // 7395 contributed to BOTH 7390 and 7400 (overlap).
  // Buckets are $10 multiples only.
  for (const p of binned[0].profile) assert.equal(p.strike % 10, 0);
});

test("binFramesToTens: a bucket needs at least one real (non-interpolated) member", () => {
  const frames: FrameLike[] = [
    {
      profile: [
        { strike: 7400, net_gex: 100, net_dex: 5, interpolated: true },
        { strike: 7405, net_gex: 50, net_dex: 2, interpolated: true },
        // 7390 region is purely interpolated → no real bucket there.
        { strike: 7195, net_gex: 10, net_dex: 1, interpolated: false },
      ],
    },
  ];
  const binned = binFramesToTens(frames);
  const strikes = binned[0].profile.map((p) => p.strike).sort((a, b) => a - b);
  // 7200 bucket exists (7195 is real); 7400/7410 buckets dropped (all interp).
  assert.ok(strikes.includes(7200));
  assert.ok(!strikes.includes(7400));
});

test("percentileInRange: clamps and handles degenerate range", () => {
  assert.equal(percentileInRange(5, 0, 10), 50);
  assert.equal(percentileInRange(0, 0, 10), 0);
  assert.equal(percentileInRange(10, 0, 10), 100);
  assert.equal(percentileInRange(15, 0, 10), 100); // clamp high
  assert.equal(percentileInRange(-5, 0, 10), 0); // clamp low
  assert.equal(percentileInRange(5, 5, 5), 0); // zero-width
});

test("buildStrikeModel: latest value, session min/max, sorting (GEX + DEX)", () => {
  const frames = [
    frame([
      [7400, 100, 10],
      [7390, -50, -5],
    ]),
    frame([
      [7400, 300, 20],
      [7390, -200, -8],
    ]),
    frame([
      [7400, 200, 15], // latest
      [7390, -100, -6],
    ]),
  ];
  const m = buildStrikeModel(frames);

  // Sorted descending by price.
  assert.deepEqual(
    m.strikes.map((s) => s.price),
    [7400, 7390],
  );

  const top = m.strikes[0];
  assert.equal(top.gex.absCurrent, 200); // last frame
  assert.equal(top.gex.absLow, 100); // session min
  assert.equal(top.gex.absHigh, 300); // session max
  assert.equal(top.dex.absCurrent, 15); // latest DEX
  assert.equal(top.dex.absLow, 10); // DEX session min
  assert.equal(top.dex.absHigh, 20); // DEX session max

  assert.equal(m.gexMaxAbs, 300);
  assert.equal(m.dexMaxAbs, 20);
  assert.ok(Math.abs(top.gex.current - 200 / 300) < 1e-12);
  assert.ok(Math.abs(top.dex.current - 15 / 20) < 1e-12);
});

test("buildStrikeModel: 5m diff uses value 5 frames back (or earliest)", () => {
  const frames = [
    frame([[7400, 100, 0]]),
    frame([[7400, 150, 0]]),
    frame([[7400, 400, 0]]),
  ];
  const m = buildStrikeModel(frames);
  assert.equal(m.strikes[0].gex.diff5m, 300); // 400 - 100
  assert.equal(m.strikes[0].gex.diff5mNorm, 1); // diffMax == 300
});

test("buildStrikeModel: ignores interpolated rows", () => {
  const frames: FrameLike[] = [
    {
      profile: [
        { strike: 7400, net_gex: 999, net_dex: 0, interpolated: true },
        { strike: 7390, net_gex: 50, net_dex: 1, interpolated: false },
      ],
    },
  ];
  const m = buildStrikeModel(frames);
  assert.deepEqual(
    m.strikes.map((s) => s.price),
    [7390],
  );
});

test("buildStrikeModel: empty input is safe (scales default to 1)", () => {
  const m = buildStrikeModel([]);
  assert.equal(m.strikes.length, 0);
  assert.equal(m.gexMaxAbs, 1);
  assert.equal(m.dexMaxAbs, 1);
});

test("meanCurrent: averages normalized current per metric", () => {
  const frames = [
    frame([
      [7400, 100, 4], // gex norm 1.0, dex norm 1.0 (maxAbs 100 / 4)
      [7390, -100, -4], // gex norm -1.0, dex norm -1.0
    ]),
  ];
  const m = buildStrikeModel(frames);
  assert.equal(meanCurrent(m.strikes, "gex"), 0); // (1 + -1)/2
  assert.equal(meanCurrent(m.strikes, "dex"), 0);
  assert.equal(meanCurrent([], "gex"), 0);
});

test("sviTotalVariance: at the vertex k=m equals a + b·sigma", () => {
  const p = { svi_a: 0.04, svi_b: 0.2, svi_rho: -0.5, svi_m: 0, svi_sigma: 0.1 };
  assert.ok(Math.abs(sviTotalVariance(0, p) - (0.04 + 0.2 * 0.1)) < 1e-12);
});

test("buildSmile: self-normalizes to [0,1] across strikes", () => {
  const p = { svi_a: 0.04, svi_b: 0.2, svi_rho: -0.8, svi_m: 0, svi_sigma: 0.05 };
  const strikes = [{ price: 7500 }, { price: 7400 }, { price: 7300 }];
  const smile = buildSmile(strikes, 7400, p);
  assert.ok(smile);
  const norms = smile!.map((s) => s.norm);
  assert.ok(Math.min(...norms) === 0);
  assert.ok(Math.max(...norms) === 1);
  assert.equal(smile!.length, 3);
});

test("buildSmile: returns null for degenerate forward/strikes", () => {
  const p = { svi_a: 0.04, svi_b: 0.2, svi_rho: -0.5, svi_m: 0, svi_sigma: 0.1 };
  assert.equal(buildSmile([{ price: 7400 }], 0, p), null);
  assert.equal(buildSmile([], 7400, p), null);
});
