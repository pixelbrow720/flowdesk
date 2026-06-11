/**
 * Offline mock feed for the realtime layer. Implements the same
 * `RealtimeSocket` surface as a real WebSocket and is injected into the
 * `RealtimeClient` as a `socketFactory`, so the EXACT same client/reducer drive
 * both live and offline modes — only the socket source differs.
 *
 * It replays a session's frames on a timer (one per `intervalMs`), emits a
 * `ping` partway through so pong handling is exercised, and can inject a STALE
 * frame to demo the feed-gap hold behavior.
 */
import type { Snapshot } from "@flowdesk/contracts";
import type { RealtimeSocket, SocketFactory } from "./client";

export interface MockFeedOptions {
  /** Frames to replay (e.g. a session from replay-mock). */
  frames: Snapshot[];
  /** ms between frames. Default 1000. */
  intervalMs?: number;
  /** Insert a STALE frame after this many frames (demo). */
  staleAfter?: number;
  /** Loop back to the start when frames run out. Default true. */
  loop?: boolean;
}

/** A timer-driven fake socket that emits snapshot/ping frames. */
class MockFeedSocket implements RealtimeSocket {
  onopen: ((this: unknown, ev: unknown) => unknown) | null = null;
  onmessage: ((this: unknown, ev: { data: unknown }) => unknown) | null = null;
  onclose: ((this: unknown, ev: { code: number }) => unknown) | null = null;
  onerror: ((this: unknown, ev: unknown) => unknown) | null = null;

  private timer: ReturnType<typeof setInterval> | null = null;
  private i = 0;
  private readonly frames: Snapshot[];
  private readonly intervalMs: number;
  private readonly staleAfter: number | undefined;
  private readonly loop: boolean;

  constructor(opts: MockFeedOptions) {
    this.frames = opts.frames;
    this.intervalMs = opts.intervalMs ?? 1000;
    this.staleAfter = opts.staleAfter;
    this.loop = opts.loop ?? true;
    // Open + send the first frame on the next microtask (mimic async connect).
    queueMicrotask(() => this.open());
  }

  private send_(frame: unknown): void {
    this.onmessage?.call(this, { data: JSON.stringify(frame) });
  }

  private open(): void {
    this.onopen?.call(this, {});
    const first = this.frames[0];
    if (first) this.send_({ type: "snapshot", data: first });
    this.i = 1;
    this.timer = setInterval(() => this.tick(), this.intervalMs);
  }

  private tick(): void {
    // Periodically exercise the heartbeat path.
    if (this.i % 5 === 0) this.send_({ type: "ping" });

    if (this.staleAfter !== undefined && this.i === this.staleAfter) {
      const base = this.frames[Math.min(this.i, this.frames.length - 1)];
      if (base) {
        this.send_({
          type: "snapshot",
          data: { ...base, state: "STALE", stale: true },
        });
      }
      this.i += 1;
      return;
    }

    if (this.i >= this.frames.length) {
      if (!this.loop) return;
      this.i = 0;
    }
    const frame = this.frames[this.i];
    if (frame) this.send_({ type: "snapshot", data: frame });
    this.i += 1;
  }

  send(_data: string): void {
    // Pong arrives here; nothing to do for the mock.
  }

  close(code = 1000): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    this.onclose?.call(this, { code });
  }
}

/** Build a `socketFactory` that produces mock-feed sockets. */
export function mockFeedFactory(opts: MockFeedOptions): SocketFactory {
  return () => new MockFeedSocket(opts);
}
