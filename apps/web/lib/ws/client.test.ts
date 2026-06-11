import { describe, it, expect } from "vitest";
import type { Snapshot } from "@flowdesk/contracts";
import { RealtimeClient, wsUrl, type RealtimeSocket } from "./client";
import type { RealtimeState } from "./reducer";

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

/** A controllable fake socket: the test drives open/message/close manually. */
class FakeSocket implements RealtimeSocket {
  onopen: ((this: unknown, ev: unknown) => unknown) | null = null;
  onmessage: ((this: unknown, ev: { data: unknown }) => unknown) | null = null;
  onclose: ((this: unknown, ev: { code: number }) => unknown) | null = null;
  onerror: ((this: unknown, ev: unknown) => unknown) | null = null;
  sent: string[] = [];
  closed = false;

  send(data: string): void {
    this.sent.push(data);
  }
  close(): void {
    this.closed = true;
  }
  // test helpers
  fireOpen(): void {
    this.onopen?.call(this, {});
  }
  fireFrame(obj: unknown): void {
    this.onmessage?.call(this, { data: JSON.stringify(obj) });
  }
  fireClose(code: number): void {
    this.onclose?.call(this, { code });
  }
}

/** A manual timer the test can flush, replacing setTimeout in the client. */
function manualTimer() {
  const pending: Array<{ fn: () => void; ms: number }> = [];
  const setTimer = (fn: () => void, ms: number) => {
    const entry = { fn, ms };
    pending.push(entry);
    return () => {
      const i = pending.indexOf(entry);
      if (i >= 0) pending.splice(i, 1);
    };
  };
  const flush = () => {
    const due = pending.splice(0, pending.length);
    for (const e of due) e.fn();
  };
  return { setTimer, flush, pending };
}

describe("wsUrl", () => {
  it("appends instrument query", () => {
    expect(wsUrl("ws://h/ws", "ES")).toBe("ws://h/ws?instrument=ES");
    expect(wsUrl("ws://h/ws?x=1", "NQ")).toBe("ws://h/ws?x=1&instrument=NQ");
  });
});

describe("RealtimeClient (fake socket)", () => {
  it("applies snapshots and replies pong to ping", () => {
    const sockets: FakeSocket[] = [];
    const states: RealtimeState[] = [];
    const client = new RealtimeClient({
      url: "ws://x/ws",
      socketFactory: () => {
        const s = new FakeSocket();
        sockets.push(s);
        return s;
      },
      onState: (s) => states.push(s),
    });
    client.start();
    const sock = sockets[0]!;
    sock.fireOpen();
    sock.fireFrame({ type: "snapshot", data: snap({ minute_index: 4 }) });
    sock.fireFrame({ type: "ping" });

    expect(client.getState().lastSnapshot?.minute_index).toBe(4);
    expect(sock.sent).toContain(JSON.stringify({ type: "pong" }));
  });

  it("holds last good frame on STALE then recovers", () => {
    const sockets: FakeSocket[] = [];
    const client = new RealtimeClient({
      url: "ws://x/ws",
      socketFactory: () => {
        const s = new FakeSocket();
        sockets.push(s);
        return s;
      },
      onState: () => {},
    });
    client.start();
    const sock = sockets[0]!;
    sock.fireOpen();
    sock.fireFrame({ type: "snapshot", data: snap({ minute_index: 4 }) });
    sock.fireFrame({
      type: "snapshot",
      data: snap({ minute_index: 5, state: "STALE", stale: true }),
    });
    expect(client.getState().stale).toBe(true);
    expect(client.getState().lastSnapshot?.minute_index).toBe(4); // held
    sock.fireFrame({ type: "snapshot", data: snap({ minute_index: 6 }) });
    expect(client.getState().stale).toBe(false);
    expect(client.getState().lastSnapshot?.minute_index).toBe(6);
  });

  it("reconnects after a transient close (new socket created)", () => {
    const sockets: FakeSocket[] = [];
    const timer = manualTimer();
    const client = new RealtimeClient({
      url: "ws://x/ws",
      socketFactory: () => {
        const s = new FakeSocket();
        sockets.push(s);
        return s;
      },
      onState: () => {},
      setTimer: timer.setTimer,
    });
    client.start();
    sockets[0]!.fireOpen();
    sockets[0]!.fireClose(1006); // transient drop
    expect(client.getState().status).toBe("reconnecting");
    expect(timer.pending.length).toBe(1);
    timer.flush(); // fire the reconnect timer
    expect(sockets.length).toBe(2); // a new socket was created
  });

  it("does NOT reconnect on a 4403 denial", () => {
    const sockets: FakeSocket[] = [];
    const timer = manualTimer();
    const client = new RealtimeClient({
      url: "ws://x/ws",
      socketFactory: () => {
        const s = new FakeSocket();
        sockets.push(s);
        return s;
      },
      onState: () => {},
      setTimer: timer.setTimer,
    });
    client.start();
    sockets[0]!.fireOpen();
    sockets[0]!.fireClose(4403);
    expect(client.getState().authError).toBe("NO_DESK");
    expect(timer.pending.length).toBe(0); // no reconnect scheduled
    expect(sockets.length).toBe(1);
  });

  it("stop() prevents reconnect", () => {
    const sockets: FakeSocket[] = [];
    const timer = manualTimer();
    const client = new RealtimeClient({
      url: "ws://x/ws",
      socketFactory: () => {
        const s = new FakeSocket();
        sockets.push(s);
        return s;
      },
      onState: () => {},
      setTimer: timer.setTimer,
    });
    client.start();
    sockets[0]!.fireOpen();
    client.stop();
    expect(sockets[0]!.closed).toBe(true);
    // A close arriving after stop must not schedule a reconnect.
    sockets[0]!.fireClose(1006);
    expect(timer.pending.length).toBe(0);
  });
});
