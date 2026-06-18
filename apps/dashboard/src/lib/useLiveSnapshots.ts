"use client";

/**
 * useLiveSnapshots — live snapshot feed for the dashboard with graceful fallback.
 *
 * Source priority (chosen 2026-06-18):
 *   1. WebSocket  /ws?instrument=…   — real-time, one frame per minute (+ on connect).
 *   2. REST       /api/snapshot      — initial seed / recovery when WS can't open.
 *   3. Static     /data/<I>_<date>.json — last resort when the API is down (dev).
 *
 * The WS protocol delivers ONE snapshot at a time, but the fog page needs the
 * whole session (per-strike min/max + 5-min momentum ride on the frame history).
 * So this hook ACCUMULATES live frames into an array, deduped/replaced by
 * `minute_index` and kept sorted — the array grows minute by minute exactly like
 * a real session. The static fallback seeds the full array in one shot.
 *
 * Auth: the WS + REST endpoints are DESK-gated by the signed session cookie. In
 * dev without a session the WS closes with 4401/4403 and REST 401s; the hook
 * then drops to the static file so the terminal still renders.
 */

import { useEffect, useRef, useState } from "react";
import {
  type Instrument,
  type Snapshot,
  isSnapshot,
  snapshotUrlFor,
  staticUrlFor,
  wsUrlFor,
} from "@/lib/api";

export type FeedStatus =
  | "connecting" // opening the socket
  | "waiting" // socket open, but no frame has arrived yet (e.g. pre-RTH / idle)
  | "live" // socket open AND at least one frame received
  | "polling" // WS unavailable; REST seeded a frame
  | "static" // API down; replaying a bundled session file
  | "error"; // no source reachable at all

const MAX_FRAMES = 500; // ~RTH minutes; matches the API replay LIMIT
const POLL_INTERVAL_MS = 30_000; // snapshots are per-minute; 30s is comfortable
const WS_RECONNECT_BASE_MS = 1_000;
const WS_RECONNECT_MAX_MS = 15_000;
// WS close codes that mean "don't retry the socket, fall back" (see api/ws.py).
const WS_FATAL_CODES = new Set([4401, 4403, 4429, 1011]);

/** Insert/replace `frame` into `frames` keyed by minute_index, kept sorted. */
function accumulate(frames: Snapshot[], frame: Snapshot): Snapshot[] {
  const next = frames.filter((f) => f.minute_index !== frame.minute_index);
  next.push(frame);
  next.sort((a, b) => a.minute_index - b.minute_index);
  return next.length > MAX_FRAMES ? next.slice(next.length - MAX_FRAMES) : next;
}

export function useLiveSnapshots(
  instrument: Instrument,
  fallbackDate: string,
  enabled: boolean = true,
): { frames: Snapshot[]; status: FeedStatus } {
  const [frames, setFrames] = useState<Snapshot[]>([]);
  const [status, setStatus] = useState<FeedStatus>("connecting");

  // Mutable refs so the effect's inner closures see current state without
  // re-subscribing on every frame.
  const framesRef = useRef<Snapshot[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // Disabled (e.g. REPLAY mode owns the terminal): open no socket, hold no
    // frames. The consumer reads from the replay hook instead.
    if (!enabled) {
      framesRef.current = [];
      setFrames([]);
      return;
    }
    let cancelled = false;
    let attempts = 0;
    framesRef.current = [];
    setFrames([]);
    setStatus("connecting");

    const pushFrame = (snap: Snapshot) => {
      framesRef.current = accumulate(framesRef.current, snap);
      setFrames(framesRef.current);
    };

    const clearTimers = () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current);
        reconnectRef.current = null;
      }
    };

    // ---- Tier 3: static session JSON (last resort) --------------------- //
    const loadStatic = async () => {
      if (cancelled) return;
      try {
        const res = await fetch(staticUrlFor(instrument, fallbackDate));
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: unknown = await res.json();
        if (cancelled) return;
        const arr = Array.isArray(data) ? data.filter(isSnapshot) : [];
        if (arr.length === 0) throw new Error("empty static snapshot array");
        framesRef.current = arr.slice(-MAX_FRAMES);
        setFrames(framesRef.current);
        setStatus("static");
      } catch (err) {
        if (cancelled) return;
        console.warn("[useLiveSnapshots] static fallback failed:", err);
        setStatus("error");
      }
    };

    // ---- Tier 2: REST polling (recovery when WS can't open) ------------ //
    const pollOnce = async () => {
      try {
        const res = await fetch(snapshotUrlFor(instrument), {
          credentials: "include",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: unknown = await res.json();
        if (cancelled) return;
        if (isSnapshot(data)) {
          pushFrame(data);
          setStatus("polling");
        }
      } catch (err) {
        // REST unavailable too -> drop to static once, then stop polling.
        if (cancelled) return;
        console.warn("[useLiveSnapshots] REST poll failed:", err);
        clearTimers();
        void loadStatic();
      }
    };

    const startPolling = () => {
      if (cancelled || pollRef.current) return;
      void pollOnce();
      pollRef.current = setInterval(() => void pollOnce(), POLL_INTERVAL_MS);
    };

    // ---- Tier 1: WebSocket (primary, real-time) ------------------------ //
    const connectWs = () => {
      if (cancelled) return;
      let ws: WebSocket;
      try {
        ws = new WebSocket(wsUrlFor(instrument));
      } catch (err) {
        console.warn("[useLiveSnapshots] WS construct failed:", err);
        startPolling();
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        if (cancelled) return;
        attempts = 0; // reset backoff on a clean open
        // Socket is up, but no data has arrived yet. Do NOT claim "live" until a
        // frame actually lands — pre-RTH / idle sessions legitimately send none.
        setStatus((s) => (s === "live" ? s : "waiting"));
      };

      ws.onmessage = (event) => {
        if (cancelled) return;
        let msg: { type?: string; data?: unknown };
        try {
          msg = JSON.parse(event.data as string);
        } catch {
          return; // ignore non-JSON frames
        }
        if (msg.type === "ping") {
          try {
            ws.send(JSON.stringify({ type: "pong" }));
          } catch {
            /* socket closing — ignore */
          }
          return;
        }
        if (msg.type === "snapshot" && isSnapshot(msg.data)) {
          pushFrame(msg.data);
          setStatus("live");
        }
      };

      ws.onclose = (event) => {
        if (cancelled) return;
        wsRef.current = null;
        // Auth/policy closes: don't hammer the socket — fall back to REST/static.
        if (WS_FATAL_CODES.has(event.code)) {
          startPolling();
          return;
        }
        // Transient close: reconnect with capped exponential backoff, but only
        // while we have no working alternative running.
        attempts += 1;
        const delay = Math.min(
          WS_RECONNECT_BASE_MS * 2 ** (attempts - 1),
          WS_RECONNECT_MAX_MS,
        );
        // After a few failed reconnects, seed from REST so the UI isn't stuck.
        if (attempts >= 3 && framesRef.current.length === 0) startPolling();
        reconnectRef.current = setTimeout(connectWs, delay);
      };

      ws.onerror = () => {
        // onerror is always followed by onclose; let onclose drive the fallback.
        try {
          ws.close();
        } catch {
          /* already closing */
        }
      };
    };

    connectWs();

    return () => {
      cancelled = true;
      clearTimers();
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch {
          /* ignore */
        }
        wsRef.current = null;
      }
    };
  }, [instrument, fallbackDate, enabled]);

  return { frames, status };
}
