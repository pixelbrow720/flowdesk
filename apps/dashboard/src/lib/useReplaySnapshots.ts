"use client";

/**
 * useReplaySnapshots — VCR-style replay of a recorded historical session.
 *
 * The Fog panels draw from a `frames` array that grows minute-by-minute, so a
 * replay is just an index ("playhead") walking a fixed array of recorded
 * snapshots: we hand the panels `allFrames.slice(0, playhead + 1)` and they
 * render exactly as if a live session were unfolding. No panel changes needed.
 *
 * Source: the same static session JSON the live hook falls back to
 * (`/data/<I>_<date>.json`) — an array of per-minute Snapshots. Loading it is
 * zero-risk (no WebSocket, no API, no Databento), which is the whole point:
 * scrub/play a known-good session to sanity-check the terminal.
 *
 * Playback: when playing, the playhead auto-advances one frame every
 * `1000 / speed` ms — 1× = one session minute per real second (the requested
 * default), 2× = 0.5s, 4× = 0.25s. It pauses automatically at the last frame.
 * All index math is the pure, unit-tested `playback.ts`.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  type Instrument,
  type Snapshot,
  isSnapshot,
  staticUrlFor,
} from "@/lib/api";
import {
  type Speed,
  advancePlayhead,
  clampPlayhead,
  playStartIndex,
  speedToIntervalMs,
  stepPlayhead,
} from "@/lib/playback";

export type ReplayStatus =
  | "loading" // fetching the session JSON
  | "ready" // loaded, paused
  | "playing" // loaded, auto-advancing
  | "error"; // session JSON unreachable / empty

export interface ReplayControls {
  /** Frames from the session start up to and including the playhead. */
  frames: Snapshot[];
  /** Total recorded frames in the session (the full array length). */
  total: number;
  /** Current 0-based frame index. */
  playhead: number;
  /** Whether the auto-advance loop is running. */
  playing: boolean;
  /** Current playback speed multiplier. */
  speed: Speed;
  status: ReplayStatus;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  stepForward: () => void;
  stepBack: () => void;
  /** Jump to an arbitrary frame index (scrubber); pauses playback. */
  seek: (index: number) => void;
  setSpeed: (speed: Speed) => void;
}

export function useReplaySnapshots(
  instrument: Instrument,
  date: string,
  enabled: boolean,
): ReplayControls {
  const [all, setAll] = useState<Snapshot[]>([]);
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeedState] = useState<Speed>(1);
  const [status, setStatus] = useState<ReplayStatus>("loading");

  const total = all.length;

  // -- load the recorded session JSON (once per instrument/date while enabled) //
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setStatus("loading");
    setAll([]);
    setPlayhead(0);
    setPlaying(false);

    (async () => {
      try {
        const res = await fetch(staticUrlFor(instrument, date));
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: unknown = await res.json();
        if (cancelled) return;
        const arr = Array.isArray(data) ? data.filter(isSnapshot) : [];
        if (arr.length === 0) throw new Error("empty session array");
        setAll(arr);
        setStatus("ready");
      } catch (err) {
        if (cancelled) return;
        console.warn("[useReplaySnapshots] session load failed:", err);
        setStatus("error");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [instrument, date, enabled]);

  // -- auto-advance loop ------------------------------------------------------ //
  // A ref holds the latest total so the interval closure stays correct without
  // re-arming the timer on every frame advance.
  const totalRef = useRef(total);
  totalRef.current = total;

  useEffect(() => {
    if (!enabled || !playing || total === 0) return;
    const id = setInterval(() => {
      setPlayhead((p) => {
        const next = advancePlayhead(p, totalRef.current);
        if (next === p) {
          // Parked at the end — stop the loop.
          setPlaying(false);
          return p;
        }
        return next;
      });
    }, speedToIntervalMs(speed));
    return () => clearInterval(id);
  }, [enabled, playing, speed, total]);

  // -- controls --------------------------------------------------------------- //
  const play = useCallback(() => {
    if (total === 0) return;
    setPlayhead((p) => playStartIndex(p, total));
    setPlaying(true);
  }, [total]);

  const pause = useCallback(() => setPlaying(false), []);

  const toggle = useCallback(() => {
    if (playing) {
      setPlaying(false);
    } else {
      if (total === 0) return;
      setPlayhead((p) => playStartIndex(p, total));
      setPlaying(true);
    }
  }, [playing, total]);

  const stepForward = useCallback(() => {
    setPlaying(false);
    setPlayhead((p) => stepPlayhead(p, +1, totalRef.current));
  }, []);

  const stepBack = useCallback(() => {
    setPlaying(false);
    setPlayhead((p) => stepPlayhead(p, -1, totalRef.current));
  }, []);

  const seek = useCallback((index: number) => {
    setPlaying(false);
    setPlayhead(clampPlayhead(index, totalRef.current));
  }, []);

  const setSpeed = useCallback((s: Speed) => setSpeedState(s), []);

  // Frames from session start up to and including the playhead.
  const frames = useMemo(
    () => (total === 0 ? [] : all.slice(0, playhead + 1)),
    [all, playhead, total],
  );

  const resolvedStatus: ReplayStatus =
    status === "ready" && playing ? "playing" : status;

  return {
    frames,
    total,
    playhead,
    playing,
    speed,
    status: resolvedStatus,
    play,
    pause,
    toggle,
    stepForward,
    stepBack,
    seek,
    setSpeed,
  };
}
