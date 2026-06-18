"use client";

/**
 * useTerminalFeed — the shared feed/control state every lens runs on.
 *
 * Bundles the LIVE-vs-REPLAY mode switch, the ES/NQ instrument switch, and the
 * two underlying hooks (`useLiveSnapshots` + `useReplaySnapshots`) into one
 * object so Fog / Flux / Arc all consume frames the exact same way. Whichever
 * mode is active owns the terminal; the other hook is disabled (no socket / no
 * fetch) so nothing runs in the background.
 *
 * Returns the active `frames` array (growing minute-by-minute, identical shape
 * in both modes), a normalized `FeedStatus`, the replay transport, and the
 * derived `latest` / `awaitingData` the chrome needs.
 */

import { useMemo, useState } from "react";
import {
  type Instrument,
  type Snapshot,
} from "@/lib/api";
import { useLiveSnapshots, type FeedStatus } from "@/lib/useLiveSnapshots";
import { useReplaySnapshots, type ReplayControls } from "@/lib/useReplaySnapshots";

export type TerminalMode = "live" | "replay";

export interface TerminalFeed {
  mode: TerminalMode;
  setMode: (m: TerminalMode) => void;
  instrument: Instrument;
  setInstrument: (i: Instrument) => void;
  frames: Snapshot[];
  status: FeedStatus;
  latest: Snapshot | null;
  awaitingData: boolean;
  replay: ReplayControls;
}

export function useTerminalFeed(
  defaultInstrument: Instrument,
  sessionDate: string,
): TerminalFeed {
  const [mode, setMode] = useState<TerminalMode>("live");
  const [instrument, setInstrument] = useState<Instrument>(defaultInstrument);

  // Live owns the terminal in LIVE; replay owns it in REPLAY. The inactive one
  // is disabled so it opens no socket / does no fetch.
  const live = useLiveSnapshots(instrument, sessionDate, mode === "live");
  const replay = useReplaySnapshots(instrument, sessionDate, mode === "replay");

  const frames = mode === "replay" ? replay.frames : live.frames;

  // Normalize the replay status into the same FeedStatus vocabulary the chrome
  // (FeedBadge / AwaitingDataOverlay) already speaks.
  const status: FeedStatus =
    mode === "replay"
      ? replay.status === "error"
        ? "error"
        : replay.status === "playing"
          ? "live"
          : replay.status === "loading"
            ? "connecting"
            : "static"
      : live.status;

  const latest = frames.length > 0 ? frames[frames.length - 1] : null;
  const awaitingData = frames.length === 0 && status !== "error";

  return useMemo(
    () => ({ mode, setMode, instrument, setInstrument, frames, status, latest, awaitingData, replay }),
    [mode, instrument, frames, status, latest, awaitingData, replay],
  );
}
