"use client";

import { useCallback, useState } from "react";
import { parseSnapshot, type Instrument, type Snapshot } from "@flowdesk/contracts";
import { useDashboardStore } from "./store";

export type SessionLoadStatus = "idle" | "loading" | "loaded" | "error";

export interface UseSessionLoader {
  status: SessionLoadStatus;
  error: string | null;
  /** Fetch a real captured session and load it into the store as REPLAY frames. */
  load: (instrument: Instrument, date: string) => Promise<void>;
}

/**
 * Loads a real captured session (generated from Databento via
 * scripts/gen_session_snapshots.py and served from /public/sessions) into the
 * store as REPLAY frames. Each frame is validated against the contract via
 * parseSnapshot, so malformed data fails fast rather than rendering garbage.
 *
 * The file layout is /sessions/<INSTR>_<date>.json — a JSON array of Snapshot.
 */
export function useSessionLoader(): UseSessionLoader {
  const [status, setStatus] = useState<SessionLoadStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const enterReplay = useDashboardStore((s) => s.enterReplay);
  const setInstrument = useDashboardStore((s) => s.setInstrument);

  const load = useCallback(
    async (instrument: Instrument, date: string) => {
      setStatus("loading");
      setError(null);
      try {
        const res = await fetch(`/sessions/${instrument}_${date}.json`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const raw: unknown = await res.json();
        if (!Array.isArray(raw) || raw.length === 0) {
          throw new Error("empty or non-array session file");
        }
        const frames: Snapshot[] = raw.map((f) => parseSnapshot(f));
        // Align the store instrument first so axis/step match the frames.
        setInstrument(instrument);
        enterReplay(date, frames);
        setStatus("loaded");
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setStatus("error");
      }
    },
    [enterReplay, setInstrument],
  );

  return { status, error, load };
}

/** Available captured sessions (extend as more are generated). */
export const REAL_SESSIONS: { instrument: Instrument; date: string }[] = [
  { instrument: "ES", date: "2026-06-09" },
  { instrument: "NQ", date: "2026-06-09" },
];
