"use client";

import { useEffect } from "react";
import { useDashboardStore } from "./store";
import { RealtimeClient, wsUrl, type SocketFactory } from "./ws/client";
import { mockFeedFactory } from "./ws/mock-feed";
import { getFullSession } from "./replay-mock";
import type { ConnectionState } from "./store";

export type RealtimeSource = "live" | "mock";

export interface UseRealtimeOptions {
  /** "live" connects to /ws; "mock" replays fixtures offline. */
  source: RealtimeSource;
  /** Base WS url for live mode (e.g. ws://localhost:8000/ws). */
  baseUrl?: string;
  /** mock-feed cadence (ms). Default 1000. */
  intervalMs?: number;
  /** mock-feed: inject a STALE frame after N frames (demo). */
  staleAfter?: number;
}

/**
 * Realtime data layer (PRD #8 §7). Connects a `RealtimeClient` and bridges its
 * reduced state into the dashboard store: applies snapshots, reflects STALE
 * (holding the last good frame), and maps the connection status onto the
 * topbar `connectionState`. Terminal denials (4401/4403) set `authError`.
 *
 * Only runs while the store is in LIVE mode — REPLAY owns the snapshot itself.
 * Switching instrument or source rebuilds the connection.
 */
export function useRealtime({
  source,
  baseUrl = "ws://localhost:8000/ws",
  intervalMs = 1000,
  staleAfter,
}: UseRealtimeOptions): void {
  const instrument = useDashboardStore((s) => s.instrument);
  const mode = useDashboardStore((s) => s.mode);

  useEffect(() => {
    // REPLAY drives the snapshot itself; don't run the live feed.
    if (mode !== "LIVE") return;

    const store = useDashboardStore.getState();
    let factory: SocketFactory | undefined;
    let url = wsUrl(baseUrl, instrument);

    if (source === "mock") {
      const frames = getFullSession(instrument, "2026-06-10");
      factory = mockFeedFactory({ frames, intervalMs, staleAfter });
      url = "mock://feed";
    }

    const client = new RealtimeClient({
      url,
      socketFactory: factory,
      onState: (state) => {
        const s = useDashboardStore.getState();
        // Ignore late updates if we've left LIVE mode.
        if (s.mode !== "LIVE") return;

        if (state.lastSnapshot) s.setSnapshot(state.lastSnapshot);
        s.setStale(state.stale);

        if (state.authError) {
          s.setAuthError(state.authError);
          s.setConnectionState("OFFLINE");
          return;
        }

        const map: Record<string, ConnectionState> = {
          connecting: "CONNECTING",
          reconnecting: "CONNECTING",
          open: state.stale ? "STALE" : "LIVE",
          closed: "OFFLINE",
          denied: "OFFLINE",
        };
        s.setConnectionState(map[state.status] ?? "CONNECTING");
      },
    });

    store.setAuthError(null);
    store.setConnectionState("CONNECTING");
    client.start();
    return () => client.stop();
  }, [source, baseUrl, instrument, mode, intervalMs, staleAfter]);
}
