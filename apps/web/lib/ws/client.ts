/**
 * Live realtime client for /ws. Thin imperative shell around the pure reducer
 * (`reducer.ts`): it owns the socket + timers and delegates ALL decisions to
 * the reducer, so the logic stays unit-testable with a fake socket.
 *
 * The socket is created via an injectable `socketFactory` so tests can supply a
 * fake; in the browser the default factory builds a real WebSocket.
 */
import {
  initialRealtimeState,
  parseFrame,
  reduce,
  type RealtimeState,
} from "./reducer";

/** Minimal socket surface the client needs (a subset of WebSocket). */
export interface RealtimeSocket {
  send: (data: string) => void;
  close: (code?: number) => void;
  onopen: ((this: unknown, ev: unknown) => unknown) | null;
  onmessage: ((this: unknown, ev: { data: unknown }) => unknown) | null;
  onclose: ((this: unknown, ev: { code: number }) => unknown) | null;
  onerror: ((this: unknown, ev: unknown) => unknown) | null;
}

export type SocketFactory = (url: string) => RealtimeSocket;

export interface RealtimeClientOptions {
  url: string;
  socketFactory?: SocketFactory;
  /** Called on every state transition (host subscribes to render). */
  onState: (state: RealtimeState) => void;
  /** Schedule a timer; returns a cancel handle. Injectable for tests. */
  setTimer?: (fn: () => void, ms: number) => () => void;
}

function defaultSocketFactory(url: string): RealtimeSocket {
  return new WebSocket(url) as unknown as RealtimeSocket;
}

function defaultSetTimer(fn: () => void, ms: number): () => void {
  const id = setTimeout(fn, ms);
  return () => clearTimeout(id);
}

/**
 * Drives a single logical realtime connection (with auto-reconnect). Call
 * `start()` to connect and `stop()` to tear down. State changes are pushed to
 * `onState`.
 */
export class RealtimeClient {
  private readonly url: string;
  private readonly makeSocket: SocketFactory;
  private readonly setTimer: (fn: () => void, ms: number) => () => void;
  private readonly emit: (state: RealtimeState) => void;

  private state: RealtimeState = initialRealtimeState;
  private socket: RealtimeSocket | null = null;
  private cancelReconnect: (() => void) | null = null;
  private stopped = false;

  constructor(opts: RealtimeClientOptions) {
    this.url = opts.url;
    this.makeSocket = opts.socketFactory ?? defaultSocketFactory;
    this.setTimer = opts.setTimer ?? defaultSetTimer;
    this.emit = opts.onState;
  }

  getState(): RealtimeState {
    return this.state;
  }

  start(): void {
    this.stopped = false;
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    this.cancelReconnect?.();
    this.cancelReconnect = null;
    if (this.socket) {
      // Detach handlers so the close we trigger doesn't schedule a reconnect.
      this.socket.onopen = null;
      this.socket.onmessage = null;
      this.socket.onclose = null;
      this.socket.onerror = null;
      try {
        this.socket.close(1000);
      } catch {
        /* ignore */
      }
      this.socket = null;
    }
  }

  private setState(next: RealtimeState): void {
    this.state = next;
    this.emit(next);
  }

  private connect(): void {
    if (this.stopped) return;
    const socket = this.makeSocket(this.url);
    this.socket = socket;

    socket.onopen = () => this.dispatch({ kind: "open" });
    socket.onmessage = (ev) => {
      if (typeof ev.data !== "string") return;
      const frame = parseFrame(ev.data);
      if (frame) this.dispatch({ kind: "frame", frame });
    };
    socket.onclose = (ev) => this.dispatch({ kind: "close", code: ev.code });
    socket.onerror = () => this.dispatch({ kind: "error" });
  }

  private dispatch(event: Parameters<typeof reduce>[1]): void {
    const { state, effects } = reduce(this.state, event);
    this.setState(state);

    if (effects.sendPong && this.socket) {
      try {
        this.socket.send(JSON.stringify({ type: "pong" }));
      } catch {
        /* socket may have closed between frames */
      }
    }

    if (effects.reconnectInMs !== undefined && !this.stopped) {
      this.socket = null;
      this.cancelReconnect?.();
      this.cancelReconnect = this.setTimer(() => {
        this.cancelReconnect = null;
        this.connect();
      }, effects.reconnectInMs);
    }
  }
}

/** Build the WS URL for an instrument from a base (ws(s)://host) or relative. */
export function wsUrl(base: string, instrument: string): string {
  const sep = base.includes("?") ? "&" : "?";
  return `${base}${sep}instrument=${encodeURIComponent(instrument)}`;
}
