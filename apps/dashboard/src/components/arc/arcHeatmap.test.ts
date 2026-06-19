/**
 * Unit tests for the Arc heatmap pure helpers.
 * Runner: node --test src/components/arc/arcHeatmap.test.ts
 */

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { buildHeatmap, gammaToColor, type HeatmapFrame } from "./arcHeatmap.ts";

const fog = (price_grid: number[], gamma: number[], delta: number[]) => ({
  price_grid,
  gamma,
  delta,
});

const frame = (minute_index: number, f: HeatmapFrame["fog"]): HeatmapFrame => ({
  minute_index,
  fog: f,
});

describe("buildHeatmap", () => {
  it("returns empty grid when no frames carry fog", () => {
    const frames = [frame(0, null), frame(1, null)];
    const hm = buildHeatmap(frames);
    assert.deepEqual(hm.prices, []);
    assert.deepEqual(hm.minutes, []);
    assert.deepEqual(hm.grid, []);
  });

  it("builds a grid aligned to the first non-empty price_grid", () => {
    const frames = [
      frame(0, fog([100, 200, 300], [1, 2, 3], [0, 0, 0])),
      frame(1, fog([100, 200, 300], [4, 5, 6], [0, 0, 0])),
    ];
    const hm = buildHeatmap(frames);
    assert.deepEqual(hm.prices, [100, 200, 300]);
    assert.deepEqual(hm.minutes, [0, 1]);
    assert.equal(hm.grid.length, 2);
    assert.deepEqual(hm.grid[0], [1, 2, 3]);
    assert.deepEqual(hm.grid[1], [4, 5, 6]);
  });

  it("sorts prices and minutes ascending", () => {
    const frames = [
      frame(5, fog([300, 100, 200], [3, 1, 2], [0, 0, 0])),
      frame(2, fog([300, 100, 200], [6, 4, 5], [0, 0, 0])),
    ];
    const hm = buildHeatmap(frames);
    assert.deepEqual(hm.prices, [100, 200, 300]);
    assert.deepEqual(hm.minutes, [2, 5]);
    assert.deepEqual(hm.grid[0], [4, 5, 6]);
    assert.deepEqual(hm.grid[1], [1, 2, 3]);
  });

  it("computes a symmetric diverging range from the absolute max gamma", () => {
    const frames = [
      frame(0, fog([100, 200], [10, -5], [0, 0])),
    ];
    const hm = buildHeatmap(frames);
    assert.equal(hm.range.min, -10);
    assert.equal(hm.range.max, 10);
  });

  it("drops frames with empty or missing fog", () => {
    const frames = [
      frame(0, null),
      frame(1, fog([100, 200], [1, 2], [0, 0])),
      frame(2, null),
      frame(3, fog([100, 200], [3, 4], [0, 0])),
    ];
    const hm = buildHeatmap(frames);
    assert.deepEqual(hm.minutes, [1, 3]);
    assert.equal(hm.grid.length, 2);
  });

  it("tolerates non-finite gamma values by leaving them null", () => {
    const frames = [
      frame(0, fog([100, 200, 300], [1, Infinity, 3], [0, 0, 0])),
    ];
    const hm = buildHeatmap(frames);
    assert.deepEqual(hm.grid[0], [1, null, 3]);
  });
});

describe("gammaToColor", () => {
  it("returns crimson at the negative extreme", () => {
    const c = gammaToColor(-10, { min: -10, max: 10 });
    assert.equal(c.r, 181);
    assert.equal(c.g, 0);
    assert.equal(c.b, 46);
  });

  it("returns turquoise at the positive extreme", () => {
    const c = gammaToColor(10, { min: -10, max: 10 });
    assert.equal(c.r, 15);
    assert.equal(c.g, 181);
    assert.equal(c.b, 168);
  });

  it("returns bone at zero (midpoint)", () => {
    const c = gammaToColor(0, { min: -10, max: 10 });
    assert.equal(c.r, 250);
    assert.equal(c.g, 250);
    assert.equal(c.b, 247);
  });

  it("returns bone for null or non-finite values", () => {
    const c1 = gammaToColor(null, { min: -10, max: 10 });
    const c2 = gammaToColor(NaN, { min: -10, max: 10 });
    const c3 = gammaToColor(Infinity, { min: -10, max: 10 });
    for (const c of [c1, c2, c3]) {
      assert.equal(c.r, 250);
      assert.equal(c.g, 250);
      assert.equal(c.b, 247);
    }
  });
});
