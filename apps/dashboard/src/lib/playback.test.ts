/**
 * Unit tests for the pure REPLAY playback math.
 *
 * Runner: Node's built-in `node:test` (no extra deps; Node strips TS types).
 * Run from apps/dashboard:
 *   node --test src/lib/playback.test.ts
 *
 * Covers the determinism-critical bits: speed→interval, clamp bounds, the
 * stop-at-end advance, ±1 step, and the play-press restart-from-end behaviour.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  SPEEDS,
  BASE_TICK_MS,
  speedToIntervalMs,
  clampPlayhead,
  isAtEnd,
  advancePlayhead,
  stepPlayhead,
  playStartIndex,
} from "./playback.ts";

test("speedToIntervalMs: 1× is one real second per session minute", () => {
  assert.equal(speedToIntervalMs(1), BASE_TICK_MS);
  assert.equal(speedToIntervalMs(2), 500);
  assert.equal(speedToIntervalMs(4), 250);
});

test("SPEEDS are the offered multipliers", () => {
  assert.deepEqual([...SPEEDS], [1, 2, 4]);
});

test("clampPlayhead bounds into [0, total-1] and truncates", () => {
  assert.equal(clampPlayhead(-5, 390), 0);
  assert.equal(clampPlayhead(0, 390), 0);
  assert.equal(clampPlayhead(389, 390), 389);
  assert.equal(clampPlayhead(1000, 390), 389);
  assert.equal(clampPlayhead(12.9, 390), 12);
});

test("clampPlayhead is safe for empty / non-finite", () => {
  assert.equal(clampPlayhead(5, 0), 0);
  assert.equal(clampPlayhead(NaN, 390), 0);
  assert.equal(clampPlayhead(Infinity, 390), 389);
});

test("isAtEnd true only on the last frame (or empty)", () => {
  assert.equal(isAtEnd(388, 390), false);
  assert.equal(isAtEnd(389, 390), true);
  assert.equal(isAtEnd(0, 0), true);
});

test("advancePlayhead steps by one and stops at the end", () => {
  assert.equal(advancePlayhead(0, 390), 1);
  assert.equal(advancePlayhead(388, 390), 389);
  // Parked at the end: stays put (the caller pauses on no-progress).
  assert.equal(advancePlayhead(389, 390), 389);
});

test("stepPlayhead moves ±1 and clamps at both ends", () => {
  assert.equal(stepPlayhead(10, +1, 390), 11);
  assert.equal(stepPlayhead(10, -1, 390), 9);
  assert.equal(stepPlayhead(0, -1, 390), 0);
  assert.equal(stepPlayhead(389, +1, 390), 389);
});

test("playStartIndex restarts from 0 when parked at the end", () => {
  assert.equal(playStartIndex(389, 390), 0); // at end → restart
  assert.equal(playStartIndex(0, 390), 0); // fresh → from start
  assert.equal(playStartIndex(120, 390), 120); // mid → resume in place
});
