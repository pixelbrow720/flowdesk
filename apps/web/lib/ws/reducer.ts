/**
 * Pure realtime reducer for the FlowDesk WS protocol (PRD #8 §7).
 *
 * Server -> client frames (JSON text):
 *   { "type": "snapshot", "data": <Snapshot> }   // connect + every minute
 *   { "type": "ping" }                            // heartbeat (~15s)
 * Client -> server:
 *   { "type": "pong" }                            // reply to ping
 *
 * STALE: a snapshot with `stale === true` (state "STALE") means the upstream
 * feed gapped. We HOLD the last good frame and surface a stale indicator until
 * a frame with `stale === false` arrives (PRD #9). The reducer keeps
 * `lastSnapshot` pointing at the most recent frame to render (which is the
 * held last-good frame while stale).
 *
 * Close codes: 4401 no session (re-login), 4403 no DESK, 4400 bad instrument,
 * 1011 service unavailable. Anything else is a transient drop -> reconnect with
 * exponential backoff 1s, 2s, 4s, ... capped at 30s.
 *
 * This module is pure (no sockets, no timers) so it can be unit-tested with a
 * fake socket and drives both the live client and the mock feed.
 */
import type { Snapshot } from "@flowdesk/contracts";

export type RealtimeStatus =
  | "connecting"
  | "open"
  | "reconnecting"
  | "closed"
  | "denied";

/** Why the connection was denied (terminal — no auto-reconnect). */
export type AuthError = "RELOGIN" | "NO_DESK" | null;

export interface RealtimeState {
  status: RealtimeStatus;
  /** The frame the UI should render (held last-good frame while stale). */
  lastSnapshot: Snapshot | null;
  /** True while the feed is stale (last good frame held). */
  stale: boolean;
  /** Number of consecutive reconnect attempts (0 when connected). */
  reconnectAttempt: number;
  /** Terminal auth/denial reason, or null. */
  authError: AuthError;
}

export const initialRealtimeState: RealtimeState = {
  status: "connecting",
  lastSnapshot: null,
  stale: false,
  reconnectAttempt: 0,
  authError: null,
};

/** Server->client frame shapes. */
export type ServerFrame =
  | { type: "snapshot"; data: Snapshot }
  | { type: "ping" };

export type RealtimeEvent =
  | { kind: "open" }
  | { kind: "frame"; frame: ServerFrame }
  | { kind: "close"; code: number }
  | { kind: "error" };

/** Side-effects the host should perform after applying an event. */
export interface RealtimeEffects {
  /** Send a pong frame back to the server. */
  sendPong?: boolean;
  /** Schedule a reconnect after this many ms (absent = no reconnect). */
  reconnectInMs?: number;
}

export interface ReduceResult {
  state: RealtimeState;
  effects: RealtimeEffects;
}

// WS close codes (mirror api/ws.py).
export const WS_CLOSE_NO_SESSION = 4401;
export const WS_CLOSE_NO_DESK = 4403;
export const WS_CLOSE_BAD_INSTRUMENT = 4400;
export const WS_CLOSE_UNAVAILABLE = 1011;
export const WS_CLOSE_NORMAL = 1000;

const BACKOFF_BASE_MS = 1000;
const BACKOFF_MAX_MS = 30_000;

/** Exponential backoff: 1s, 2s, 4s, ... capped at 30s. attempt is 1-based. */
export function backoffMs(attempt: number): number {
  const exp = BACKOFF_BASE_MS * 2 ** Math.max(0, attempt - 1);
  return Math.min(exp, BACKOFF_MAX_MS);
}

/** Parse a raw text frame into a typed ServerFrame, or null if invalid. */
export function parseFrame(raw: string): ServerFrame | null {
  let obj: unknown;
  try {
    obj = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof obj !== "object" || obj === null) return null;
  const t = (obj as { type?: unknown }).type;
  if (t === "ping") return { type: "ping" };
  if (t === "snapshot") {
    const data = (obj as { data?: unknown }).data;
    if (typeof data === "object" && data !== null) {
      return { type: "snapshot", data: data as Snapshot };
    }
  }
  return null;
}

/** Apply one event to the state, returning the next state + effects. */
export function reduce(state: RealtimeState, event: RealtimeEvent): ReduceResult {
  switch (event.kind) {
    case "open":
      return {
        state: { ...state, status: "open", reconnectAttempt: 0, authError: null },
        effects: {},
      };

    case "frame": {
      if (event.frame.type === "ping") {
        return { state, effects: { sendPong: true } };
      }
      // snapshot
      const snap = event.frame.data;
      const isStale = snap.stale === true || snap.state === "STALE";
      if (isStale) {
        // Hold the last good frame; only flip the stale flag. If we have no good
        // frame yet, show the stale frame so the UI isn't blank.
        return {
          state: {
            ...state,
            stale: true,
            lastSnapshot: state.lastSnapshot ?? snap,
            status: "open",
          },
          effects: {},
        };
      }
      return {
        state: { ...state, stale: false, lastSnapshot: snap, status: "open" },
        effects: {},
      };
    }

    case "close": {
      if (event.code === WS_CLOSE_NO_SESSION) {
        return {
          state: { ...state, status: "denied", authError: "RELOGIN" },
          effects: {},
        };
      }
      if (event.code === WS_CLOSE_NO_DESK) {
        return {
          state: { ...state, status: "denied", authError: "NO_DESK" },
          effects: {},
        };
      }
      if (
        event.code === WS_CLOSE_BAD_INSTRUMENT ||
        event.code === WS_CLOSE_NORMAL
      ) {
        // Terminal but not an auth problem — do not auto-reconnect.
        return { state: { ...state, status: "closed" }, effects: {} };
      }
      // Transient (incl. 1011 unavailable, network drops): reconnect w/ backoff.
      const attempt = state.reconnectAttempt + 1;
      return {
        state: { ...state, status: "reconnecting", reconnectAttempt: attempt },
        effects: { reconnectInMs: backoffMs(attempt) },
      };
    }

    case "error":
      // Treat a socket error like a transient drop; the subsequent close event
      // (if any) will schedule the reconnect. Mark reconnecting optimistically.
      return {
        state: { ...state, status: "reconnecting" },
        effects: {},
      };

    default:
      return { state, effects: {} };
  }
}
