/**
 * Unit tests for the pure Flux time-series helpers.
 * Runner: node:test. From apps/dashboard:
 *   node --test src/components/flux/fluxSeries.test.ts
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildFluxSeries,
  buildFluxMetrics,
  buildFluxModel,
  type FluxFrameLike,
} from "./fluxSeries.ts";

function frame(ts: string, flux: FluxFrameLike["flux"]): FluxFrameLike {
  return { ts, flux };
}

const fb = (total: number, calls: number, puts: number, retail: number) => ({
  total,
  calls,
  puts,
  zerodte: total,
  retail,
});

test("buildFluxSeries: emits 4 cumulative series, chronological", () => {
  const s = buildFluxSeries([
    frame("2026-06-09T14:00:00Z", fb(100, 60, 40, 30)),
    frame("2026-06-09T14:01:00Z", fb(-50, 20, -70, 10)),
  ]);
  assert.equal(s.total.length, 2);
  assert.equal(s.total[0].value, 100);
  assert.equal(s.total[1].value, -50);
  assert.equal(s.calls[1].value, 20);
  assert.equal(s.puts[1].value, -70);
  assert.equal(s.retail[0].value, 30);
  assert.ok(s.total[0].time < s.total[1].time); // chronological
});

test("buildFluxSeries: skips null-flux frames and duplicate timestamps", () => {
  const s = buildFluxSeries([
    frame("2026-06-09T14:00:00Z", fb(100, 60, 40, 30)),
    frame("2026-06-09T14:00:30Z", null), // no flux → skipped
    frame("2026-06-09T14:00:00Z", fb(999, 1, 1, 1)), // dup time → dropped
  ]);
  assert.equal(s.total.length, 1);
  assert.equal(s.total[0].value, 100);
});

test("buildFluxMetrics: latest frame, retail share + P/C ratio", () => {
  const m = buildFluxMetrics([
    frame("2026-06-09T14:00:00Z", fb(100, 60, 40, 30)),
    frame("2026-06-09T14:01:00Z", fb(200, 80, 120, 50)),
  ]);
  assert.equal(m.total, 200);
  assert.equal(m.calls, 80);
  assert.equal(m.puts, 120);
  assert.equal(m.retail, 50);
  assert.equal(m.retailShare, 25); // |50|/|200| = 25%
  assert.equal(m.pcRatio, 1.5); // |120/80|
});

test("buildFluxMetrics: falls back to latest NON-NULL flux frame", () => {
  const m = buildFluxMetrics([
    frame("2026-06-09T14:00:00Z", fb(100, 60, 40, 30)),
    frame("2026-06-09T14:01:00Z", null), // latest, but no flux
  ]);
  assert.equal(m.total, 100); // uses frame 0
});

test("buildFluxMetrics: zero total → null share; zero calls → null P/C", () => {
  const m = buildFluxMetrics([frame("2026-06-09T14:00:00Z", fb(0, 0, 0, 0))]);
  assert.equal(m.retailShare, null);
  assert.equal(m.pcRatio, null);
});

test("buildFluxModel: empty input is safe", () => {
  const m = buildFluxModel([]);
  assert.equal(m.series.total.length, 0);
  assert.equal(m.metrics.total, null);
});
