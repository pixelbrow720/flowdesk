/**
 * Unit tests for the pure levels-chart helpers (Fog right panel).
 * Runner: node:test. From apps/dashboard:
 *   node --test src/components/fog/levelsChart.test.ts
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildCandles,
  resolveKeyLevels,
  perStrikeGammaFlip,
  buildMetrics,
  buildRatios,
  buildLevelsChart,
  type LevelsFrameLike,
} from "./levelsChart.ts";

function frame(over: Partial<LevelsFrameLike> & { ts: string; forward: number }): LevelsFrameLike {
  return {
    profile: [],
    regime: { net_gamma: 0 },
    levels: { call_walls: [], put_walls: [], gamma_flip: null, largest_gex: null, largest_dex: null },
    surface: null,
    proprietary: null,
    ...over,
  };
}

test("buildCandles: open = prev close, high/low bound both, sorted+deduped", () => {
  const c = buildCandles([
    frame({ ts: "2026-06-09T14:00:00Z", forward: 7100 }),
    frame({ ts: "2026-06-09T14:01:00Z", forward: 7120 }),
    frame({ ts: "2026-06-09T14:00:00Z", forward: 9999 }), // dup time → dropped
  ]);
  assert.equal(c.length, 2);
  assert.deepEqual(c[0], { time: c[0].time, open: 7100, high: 7100, low: 7100, close: 7100 });
  assert.equal(c[1].open, 7100); // prev close
  assert.equal(c[1].close, 7120);
  assert.equal(c[1].high, 7120);
  assert.equal(c[1].low, 7100);
});

test("perStrikeGammaFlip: interpolates the +/- zone boundary, nearest forward", () => {
  // net_gex flips sign between 7350 (+) and 7355 (-): zero at the midpoint.
  const profile = [
    { strike: 7345, net_gex: 200 },
    { strike: 7350, net_gex: 100 },
    { strike: 7355, net_gex: -100 },
    { strike: 7360, net_gex: -300 },
  ];
  assert.equal(perStrikeGammaFlip(profile, 7355), 7352.5);
  // Fewer than 2 rows → null.
  assert.equal(perStrikeGammaFlip([{ strike: 7350, net_gex: 5 }], 7350), null);
  // No sign change → null.
  assert.equal(
    perStrikeGammaFlip([{ strike: 7350, net_gex: 5 }, { strike: 7355, net_gex: 7 }], 7350),
    null,
  );
});

test("resolveKeyLevels: walls FROZEN at RTH open, dynamic levels track playhead", () => {
  const frames = [
    frame({
      ts: "2026-06-09T14:00:00Z",
      forward: 7100,
      profile: [{ strike: 7095, net_gex: 50 }, { strike: 7105, net_gex: -50 }],
      levels: { call_walls: [7410, 7420], put_walls: [7350], gamma_flip: 7402, largest_gex: 7400, largest_dex: null },
    }),
    frame({
      ts: "2026-06-09T14:01:00Z",
      forward: 7105,
      profile: [{ strike: 7100, net_gex: 80 }, { strike: 7110, net_gex: -80 }],
      levels: { call_walls: [7415], put_walls: [7355], gamma_flip: null, largest_gex: 7405, largest_dex: null },
    }),
  ];
  const lv = resolveKeyLevels(frames);
  const byId = new Map(lv.map((l) => [l.id, l]));
  // Walls frozen at frame 0 (RTH open), NOT the latest frame.
  assert.equal(byId.get("call_wall")!.price, 7410);
  assert.equal(byId.get("put_wall")!.price, 7350);
  // Zero γ from the CURRENT (playhead) frame's per-strike flip: 7100(+)→7110(-) → 7105.
  assert.equal(byId.get("gamma_flip")!.price, 7105);
  // Largest GEX reads the current frame.
  assert.equal(byId.get("largest_gex")!.price, 7405);
  assert.ok(!byId.has("largest_dex")); // null on current frame → dropped
});

test("resolveKeyLevels: proprietary OI levels frozen at RTH open + flagged", () => {
  const frames = [
    frame({ ts: "2026-06-09T14:00:00Z", forward: 7100, proprietary: { oi_gamma_flip: null, abs_gamma_strike: 7400, hedge_wall: 7410 } }),
    frame({ ts: "2026-06-09T14:01:00Z", forward: 7105, proprietary: { oi_gamma_flip: 7488, abs_gamma_strike: 7401, hedge_wall: 7411 } }),
  ];
  const lv = resolveKeyLevels(frames);
  const byId = new Map(lv.map((l) => [l.id, l]));
  const hw = byId.get("hedge_wall");
  assert.ok(hw);
  assert.equal(hw!.experimental, true);
  assert.equal(hw!.price, 7410); // frozen at frame 0, not 7411
  assert.equal(byId.get("abs_gamma")!.price, 7400);
  // oi_gamma_flip: null at RTH open → frozen value is the first non-null (7488).
  assert.equal(byId.get("oi_gamma_flip")!.price, 7488);
});

test("buildMetrics: GEX long share + latest surface metrics", () => {
  const frames = [
    frame({
      ts: "2026-06-09T14:00:00Z",
      forward: 7100,
      profile: [{ net_gex: 75 }, { net_gex: -25 }], // 75 of 100 abs is positive → 75%
      regime: { net_gamma: 1.5e9 },
      surface: { atm_vol: 0.2, expected_move: 35, skew: -0.4 },
      theta_decay: { net_theta: -2.5e9, theta_sign: -1 },
      max_pain: { strike: 7100 },
      vol_expansion: { expansion: 0.08 },
    }),
  ];
  const m = buildMetrics(frames);
  assert.equal(m.gexLongShare, 75);
  assert.equal(m.netGamma, 1.5e9);
  assert.equal(m.atmVol, 0.2);
  assert.equal(m.expectedMove, 35);
  assert.equal(m.skew, -0.4);
  assert.equal(m.thetaDecay, -2.5e9);
  assert.equal(m.maxPain, 7100);
  assert.equal(m.volExpansion, 0.08);
});

test("buildMetrics: experimental fields fall back to null when absent", () => {
  const m = buildMetrics([frame({ ts: "2026-06-09T14:00:00Z", forward: 7100 })]);
  assert.equal(m.atmVol, null);
  assert.equal(m.expectedMove, null);
  assert.equal(m.skew, null);
  assert.equal(m.gexLongShare, null);
  assert.equal(m.netGamma, 0);
  assert.equal(m.thetaDecay, null);
  assert.equal(m.maxPain, null);
  assert.equal(m.volExpansion, null);
});

test("buildRatios: per-frame series, surface lines skip null-surface frames", () => {
  const frames = [
    frame({
      ts: "2026-06-09T14:00:00Z",
      forward: 7100,
      profile: [{ net_gex: 80 }, { net_gex: -20 }], // 80%
      surface: { atm_vol: 0.2, expected_move: 35, skew: -0.4 },
    }),
    frame({
      ts: "2026-06-09T14:01:00Z",
      forward: 7105,
      profile: [{ net_gex: 50 }, { net_gex: -50 }], // 50%
      surface: null, // no surface this minute
    }),
  ];
  const r = buildRatios(frames);
  // GEX share exists for both frames.
  assert.equal(r.gexLongShare.length, 2);
  assert.equal(r.gexLongShare[0].value, 80);
  assert.equal(r.gexLongShare[1].value, 50);
  // Surface lines only for the frame with a surface; atm_vol scaled to %.
  assert.equal(r.atmVol.length, 1);
  assert.equal(r.atmVol[0].value, 20);
  assert.equal(r.skew.length, 1);
  assert.equal(r.skew[0].value, -0.4);
});

test("buildLevelsChart + empty input is safe", () => {
  const m = buildLevelsChart([]);
  assert.equal(m.candles.length, 0);
  assert.equal(m.levels.length, 0);
  assert.equal(m.metrics.atmVol, null);
  assert.equal(m.ratios.gexLongShare.length, 0);
});
