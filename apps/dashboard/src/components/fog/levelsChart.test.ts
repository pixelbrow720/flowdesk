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

test("resolveKeyLevels: takes latest non-null, top wall, drops missing", () => {
  const frames = [
    frame({ ts: "2026-06-09T14:00:00Z", forward: 7100, levels: { call_walls: [7410, 7420], put_walls: [7350], gamma_flip: 7402, largest_gex: 7400, largest_dex: null } }),
    frame({ ts: "2026-06-09T14:01:00Z", forward: 7105, levels: { call_walls: [7415], put_walls: [7355], gamma_flip: null, largest_gex: 7405, largest_dex: null } }),
  ];
  const lv = resolveKeyLevels(frames);
  const byId = new Map(lv.map((l) => [l.id, l]));
  assert.equal(byId.get("call_wall")!.price, 7415); // top of latest frame
  assert.equal(byId.get("put_wall")!.price, 7355);
  assert.equal(byId.get("gamma_flip")!.price, 7402); // latest non-null (frame 0)
  assert.equal(byId.get("largest_gex")!.price, 7405);
  assert.ok(!byId.has("largest_dex")); // never present → dropped
  assert.ok(!byId.has("hedge_wall")); // proprietary null → dropped
});

test("resolveKeyLevels: experimental flag + color set on proprietary levels", () => {
  const frames = [
    frame({ ts: "2026-06-09T14:00:00Z", forward: 7100, proprietary: { oi_gamma_flip: null, abs_gamma_strike: 7400, hedge_wall: 7410 } }),
  ];
  const lv = resolveKeyLevels(frames);
  const hw = lv.find((l) => l.id === "hedge_wall");
  assert.ok(hw);
  assert.equal(hw!.experimental, true);
  assert.equal(hw!.price, 7410);
  // oi_gamma_flip is null → not present.
  assert.ok(!lv.some((l) => l.id === "oi_gamma_flip"));
});

test("buildMetrics: GEX long share + latest surface metrics", () => {
  const frames = [
    frame({
      ts: "2026-06-09T14:00:00Z",
      forward: 7100,
      profile: [{ net_gex: 75 }, { net_gex: -25 }], // 75 of 100 abs is positive → 75%
      regime: { net_gamma: 1.5e9 },
      surface: { atm_vol: 0.2, expected_move: 35, skew: -0.4 },
    }),
  ];
  const m = buildMetrics(frames);
  assert.equal(m.gexLongShare, 75);
  assert.equal(m.netGamma, 1.5e9);
  assert.equal(m.atmVol, 0.2);
  assert.equal(m.expectedMove, 35);
  assert.equal(m.skew, -0.4);
});

test("buildMetrics: null surface yields null metrics, share null on empty profile", () => {
  const m = buildMetrics([frame({ ts: "2026-06-09T14:00:00Z", forward: 7100 })]);
  assert.equal(m.atmVol, null);
  assert.equal(m.expectedMove, null);
  assert.equal(m.skew, null);
  assert.equal(m.gexLongShare, null);
  assert.equal(m.netGamma, 0);
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
