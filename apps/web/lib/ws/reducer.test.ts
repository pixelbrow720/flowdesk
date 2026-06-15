import { describe, it, expect } from "vitest";
import type { Snapshot } from "@flowdesk/contracts";
import {
  reduce,
  parseFrame,
  backoffMs,
  initialRealtimeState,
  WS_CLOSE_NO_SESSION,
  WS_CLOSE_NO_DESK,
  WS_CLOSE_BAD_INSTRUMENT,
  WS_CLOSE_UNAVAILABLE,
  WS_CLOSE_NORMAL,
  type RealtimeState,
} from "./reducer";

// Minimal contract-shaped snapshot for the reducer (it doesn't re-validate).
function snap(overrides: Partial<Snapshot> = {}): Snapshot {
  return {
    schema_version: 1,
    instrument: "ES",
    session_date: "2026-06-10",
    ts: "2026-06-10T13:31:00Z",
    minute_index: 1,
    state: "LIVE",
    stale: false,
    expired: false,
    forward: 5000,
    rate: 0.05,
    axis: { strike_min: 4990, strike_max: 5010, step: 5 },
    regime: { net_gamma: 1, sign: 1, stability_pct: 50 },
    profile: [],
    field: { price_grid: [5000], gamma: [1], delta: [1] },
    levels: {
      call_walls: [],
      put_walls: [],
      gamma_flip: null,
      largest_gex: null,
      largest_dex: null,
    },
    ...overrides,
  } as Snapshot;
}

const open = (): RealtimeState =>
  reduce(initialRealtimeState, { kind: "open" }).state;

describe("parseFrame", () => {
  it("parses ping and snapshot frames", () => {
    expect(parseFrame('{"type":"ping"}')).toEqual({ type: "ping" });
    // Post-fix contract: the snapshot branch runs `data` through
    // `safeParseSnapshot` (zod) before accepting. Feed a FULL contract-shaped
    // snapshot so validation succeeds and the parsed frame is returned.
    const raw = JSON.stringify({ type: "snapshot", data: snap() });
    const f = parseFrame(raw);
    expect(f?.type).toBe("snapshot");
    // Prove zod actually accepted it (and didn't just cast through): the
    // returned frame carries the full validated shape, not a partial stub.
    expect(f?.type === "snapshot" && f.data.schema_version).toBe(1);
    expect(f?.type === "snapshot" && f.data.instrument).toBe("ES");
    expect(f?.type === "snapshot" && f.data.minute_index).toBe(1);
  });

  it("rejects malformed snapshot data via zod", () => {
    // A partial like `{"instrument":"ES"}` is missing every other required
    // field of the Snapshot contract. Pre-fix, parseFrame cast `data as
    // Snapshot` and returned an invalid frame; post-fix, zod rejects it and
    // parseFrame returns null. This is the load-bearing anti-regression: if
    // anyone reverts the safeParseSnapshot call, this test will catch them.
    expect(
      parseFrame('{"type":"snapshot","data":{"instrument":"ES"}}'),
    ).toBeNull();
    // A snapshot envelope whose `data` violates a deep invariant (here:
    // field array-length mismatch) must also be rejected by zod.
    const bad = snap();
    (bad as { field: { gamma: number[] } }).field = {
      ...bad.field,
      gamma: [1, 2], // length 2 vs price_grid length 1 -> superRefine fails
    };
    expect(
      parseFrame(JSON.stringify({ type: "snapshot", data: bad })),
    ).toBeNull();
  });

  it("rejects malformed / unknown frames", () => {
    expect(parseFrame("not json")).toBeNull();
    expect(parseFrame('{"type":"snapshot"}')).toBeNull(); // no data
    expect(parseFrame('{"type":"bogus"}')).toBeNull();
    expect(parseFrame("123")).toBeNull();
  });
});

describe("backoffMs", () => {
  it("is 1s, 2s, 4s, ... capped at 30s", () => {
    expect(backoffMs(1)).toBe(1000);
    expect(backoffMs(2)).toBe(2000);
    expect(backoffMs(3)).toBe(4000);
    expect(backoffMs(4)).toBe(8000);
    expect(backoffMs(5)).toBe(16000);
    expect(backoffMs(6)).toBe(30000); // 32s -> capped
    expect(backoffMs(99)).toBe(30000);
  });
});

describe("reduce — snapshots + stale hold", () => {
  it("open resets attempt + auth", () => {
    const r = reduce(
      { ...initialRealtimeState, reconnectAttempt: 3, authError: "RELOGIN" },
      { kind: "open" },
    );
    expect(r.state.status).toBe("open");
    expect(r.state.reconnectAttempt).toBe(0);
    expect(r.state.authError).toBeNull();
  });

  it("applies a good snapshot as lastSnapshot, clears stale", () => {
    const r = reduce(open(), {
      kind: "frame",
      frame: { type: "snapshot", data: snap({ minute_index: 7 }) },
    });
    expect(r.state.lastSnapshot?.minute_index).toBe(7);
    expect(r.state.stale).toBe(false);
  });

  it("HOLDS the last good frame when a stale frame arrives", () => {
    let s = reduce(open(), {
      kind: "frame",
      frame: { type: "snapshot", data: snap({ minute_index: 7 }) },
    }).state;
    // Stale frame at minute 8 should NOT replace the held frame (7).
    s = reduce(s, {
      kind: "frame",
      frame: {
        type: "snapshot",
        data: snap({ minute_index: 8, state: "STALE", stale: true }),
      },
    }).state;
    expect(s.stale).toBe(true);
    expect(s.lastSnapshot?.minute_index).toBe(7); // held
    // Recovery: a fresh good frame replaces it and clears stale.
    s = reduce(s, {
      kind: "frame",
      frame: { type: "snapshot", data: snap({ minute_index: 9 }) },
    }).state;
    expect(s.stale).toBe(false);
    expect(s.lastSnapshot?.minute_index).toBe(9);
  });

  it("shows the stale frame if there is no prior good frame", () => {
    const r = reduce(open(), {
      kind: "frame",
      frame: {
        type: "snapshot",
        data: snap({ minute_index: 3, state: "STALE", stale: true }),
      },
    });
    expect(r.state.stale).toBe(true);
    expect(r.state.lastSnapshot?.minute_index).toBe(3);
  });

  it("requests a pong on ping", () => {
    const r = reduce(open(), { kind: "frame", frame: { type: "ping" } });
    expect(r.effects.sendPong).toBe(true);
    expect(r.state).toEqual(open()); // ping doesn't mutate state
  });
});

describe("reduce — close codes", () => {
  it("4401 -> denied RELOGIN, no reconnect", () => {
    const r = reduce(open(), { kind: "close", code: WS_CLOSE_NO_SESSION });
    expect(r.state.status).toBe("denied");
    expect(r.state.authError).toBe("RELOGIN");
    expect(r.effects.reconnectInMs).toBeUndefined();
  });

  it("4403 -> denied NO_DESK, no reconnect", () => {
    const r = reduce(open(), { kind: "close", code: WS_CLOSE_NO_DESK });
    expect(r.state.status).toBe("denied");
    expect(r.state.authError).toBe("NO_DESK");
    expect(r.effects.reconnectInMs).toBeUndefined();
  });

  it("4400 bad instrument + 1000 normal -> closed, no reconnect", () => {
    expect(
      reduce(open(), { kind: "close", code: WS_CLOSE_BAD_INSTRUMENT }).state.status,
    ).toBe("closed");
    expect(
      reduce(open(), { kind: "close", code: WS_CLOSE_NORMAL }).effects.reconnectInMs,
    ).toBeUndefined();
  });

  it("transient close (1011 / 1006) -> reconnecting with growing backoff", () => {
    let s = open();
    let r = reduce(s, { kind: "close", code: WS_CLOSE_UNAVAILABLE });
    expect(r.state.status).toBe("reconnecting");
    expect(r.state.reconnectAttempt).toBe(1);
    expect(r.effects.reconnectInMs).toBe(1000);

    r = reduce(r.state, { kind: "close", code: 1006 });
    expect(r.state.reconnectAttempt).toBe(2);
    expect(r.effects.reconnectInMs).toBe(2000);
  });
});
