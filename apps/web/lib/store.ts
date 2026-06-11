import { create } from "zustand";
import type { Instrument, Snapshot } from "@flowdesk/contracts";
import { MOCK_SNAPSHOTS } from "./mock-data";

/** Live connection state shown on the topbar dot (PRD #4 §4.2). */
export type ConnectionState = "LIVE" | "STALE" | "REPLAY" | "CONNECTING" | "OFFLINE";

/** Which series the profile line plots (toolbar toggle, PRD #4). */
export type ProfileMetric = "GEX" | "DEX";
/** Which field array the heatmap renders (toolbar toggle, PRD #4). */
export type HeatmapBasis = "GAMMA" | "DELTA";
/** How many Call/Put walls to overlay (key-levels picker, PRD #4). */
export type WallCount = 1 | 2 | 3;

/** Playback mode (PRD #10). LIVE tracks the newest minute; REPLAY plays stored frames. */
export type Mode = "LIVE" | "REPLAY";
/** Replay playback speed multiplier. */
export type Speed = 1 | 2 | 4;
/** Heatmap candle bin size in minutes (display only; updates stay 1-minute). */
export type CandleSize = 1 | 5;

interface DashboardState {
  instrument: Instrument;
  snapshot: Snapshot;
  connectionState: ConnectionState;
  profileMetric: ProfileMetric;
  heatmapBasis: HeatmapBasis;
  heatmapSmooth: boolean;
  wallCount: WallCount;
  /** Heatmap candle bin size (1 or 5 min). Display only; updates stay 1-min. */
  candleSize: CandleSize;
  /** Vertical zoom: points above/below center shown on both panels (PRD ~50). */
  zoomPts: number;

  /** True while the live feed is stale (last good frame held, PRD #9). */
  stale: boolean;
  /** Terminal realtime denial: "RELOGIN" (4401) | "NO_DESK" (4403) | null. */
  authError: "RELOGIN" | "NO_DESK" | null;

  // ── Replay (PRD #10) ──
  mode: Mode;
  /** Loaded replay frames for the active session (empty in LIVE). */
  frames: Snapshot[];
  /** Current frame index within `frames` (REPLAY only). */
  frameIndex: number;
  /** Active replay session date, or null in LIVE. */
  replayDate: string | null;
  playing: boolean;
  speed: Speed;

  setInstrument: (instrument: Instrument) => void;
  setSnapshot: (snapshot: Snapshot) => void;
  setConnectionState: (state: ConnectionState) => void;
  setProfileMetric: (metric: ProfileMetric) => void;
  setHeatmapBasis: (basis: HeatmapBasis) => void;
  setHeatmapSmooth: (smooth: boolean) => void;
  setWallCount: (count: WallCount) => void;
  setCandleSize: (size: CandleSize) => void;
  setZoomPts: (pts: number) => void;
  setStale: (stale: boolean) => void;
  setAuthError: (error: "RELOGIN" | "NO_DESK" | null) => void;

  enterReplay: (date: string, frames: Snapshot[]) => void;
  exitToLive: () => void;
  setFrameIndex: (i: number) => void;
  stepFrame: (delta: number) => void;
  setPlaying: (playing: boolean) => void;
  setSpeed: (speed: Speed) => void;
}

/**
 * Global dashboard store. Seeded with the validated mock snapshot so every
 * surface renders offline (no backend). Switching instrument swaps in that
 * instrument's mock until the realtime layer (4.7) overwrites it.
 *
 * Defaults follow PRD #5: instrument ES, Net GEX, Gamma basis, smooth render,
 * key-levels Wall Top 1. Starts in LIVE mode.
 */
export const useDashboardStore = create<DashboardState>((set, get) => ({
  instrument: "ES",
  snapshot: MOCK_SNAPSHOTS.ES,
  connectionState: "LIVE",
  profileMetric: "GEX",
  heatmapBasis: "GAMMA",
  heatmapSmooth: true,
  wallCount: 1,
  candleSize: 5,
  zoomPts: 50,

  stale: false,
  authError: null,

  mode: "LIVE",
  frames: [],
  frameIndex: 0,
  replayDate: null,
  playing: false,
  speed: 1,

  setInstrument: (instrument) => {
    // Switching instrument always returns to LIVE for that instrument's mock.
    set({
      instrument,
      snapshot: MOCK_SNAPSHOTS[instrument],
      mode: "LIVE",
      connectionState: "LIVE",
      frames: [],
      frameIndex: 0,
      replayDate: null,
      playing: false,
      stale: false,
      authError: null,
    });
  },
  setSnapshot: (snapshot) => set({ snapshot }),
  setConnectionState: (connectionState) => set({ connectionState }),
  setProfileMetric: (profileMetric) => set({ profileMetric }),
  setHeatmapBasis: (heatmapBasis) => set({ heatmapBasis }),
  setHeatmapSmooth: (heatmapSmooth) => set({ heatmapSmooth }),
  setWallCount: (wallCount) => set({ wallCount }),
  setCandleSize: (candleSize) => set({ candleSize }),
  setZoomPts: (pts) => set({ zoomPts: Math.max(10, Math.min(200, Math.round(pts))) }),
  setStale: (stale) => set({ stale }),
  setAuthError: (authError) => set({ authError }),

  enterReplay: (date, frames) => {
    const first = frames[0];
    if (first === undefined) return;
    set({
      mode: "REPLAY",
      connectionState: "REPLAY",
      replayDate: date,
      frames,
      frameIndex: 0,
      playing: false,
      snapshot: first,
      stale: false,
    });
  },

  exitToLive: () => {
    const { instrument } = get();
    set({
      mode: "LIVE",
      connectionState: "LIVE",
      frames: [],
      frameIndex: 0,
      replayDate: null,
      playing: false,
      snapshot: MOCK_SNAPSHOTS[instrument],
      stale: false,
    });
  },

  setFrameIndex: (i) => {
    const { frames } = get();
    if (frames.length === 0) return;
    const clamped = Math.max(0, Math.min(i, frames.length - 1));
    const frame = frames[clamped];
    if (frame === undefined) return;
    set({ frameIndex: clamped, snapshot: frame });
  },

  stepFrame: (delta) => {
    get().setFrameIndex(get().frameIndex + delta);
  },

  setPlaying: (playing) => set({ playing }),
  setSpeed: (speed) => set({ speed }),
}));
