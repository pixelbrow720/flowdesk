/**
 * playback.ts — pure, framework-free playback math for the Fog REPLAY mode.
 *
 * The replay scrubber/play loop is just an index ("playhead") walking a fixed
 * array of per-minute snapshot frames. All the index arithmetic (advance,
 * clamp, seek, step, the play-tick interval for a given speed) is pulled out
 * here as pure functions so it can be unit-tested with `node:test` without a
 * DOM or React — same convention as strikeMath.ts / levelsChart.ts.
 *
 * The React glue (timers, JSON load, state) lives in useReplaySnapshots.ts.
 */

/** Playback speeds offered in the UI: 1×/2×/4× real-minutes-per-real-second. */
export const SPEEDS = [1, 2, 4] as const;
export type Speed = (typeof SPEEDS)[number];

/** Base tick at 1×: one frame (one session minute) advances every 1000ms. */
export const BASE_TICK_MS = 1000;

/**
 * Milliseconds between auto-advances for a given speed. 1× = 1000ms (one
 * session minute per real second), 2× = 500ms, 4× = 250ms.
 */
export function speedToIntervalMs(speed: Speed): number {
  return BASE_TICK_MS / speed;
}

/** Clamp an arbitrary index into the valid `[0, total-1]` playhead range. */
export function clampPlayhead(index: number, total: number): number {
  if (total <= 0) return 0;
  if (Number.isNaN(index)) return 0;
  if (index === Infinity) return total - 1;
  if (index === -Infinity) return 0;
  const i = Math.trunc(index);
  if (i < 0) return 0;
  if (i > total - 1) return total - 1;
  return i;
}

/** True when the playhead sits on the last available frame. */
export function isAtEnd(playhead: number, total: number): boolean {
  return total <= 0 || playhead >= total - 1;
}

/**
 * Next playhead for one auto-advance tick. Stops (stays put) at the last frame
 * — the caller pauses when this returns the same index it was given.
 */
export function advancePlayhead(playhead: number, total: number): number {
  return clampPlayhead(playhead + 1, total);
}

/** Step the playhead by `delta` minutes (±1 for the step buttons), clamped. */
export function stepPlayhead(playhead: number, delta: number, total: number): number {
  return clampPlayhead(playhead + delta, total);
}

/**
 * Resolve what a "play" press should do given the current playhead. If we're
 * already parked at the end, a press restarts from 0; otherwise it resumes from
 * where we are. Returns the playhead to start playing from.
 */
export function playStartIndex(playhead: number, total: number): number {
  return isAtEnd(playhead, total) ? 0 : clampPlayhead(playhead, total);
}
