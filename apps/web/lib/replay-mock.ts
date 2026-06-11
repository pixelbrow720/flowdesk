/**
 * Replay mock data for offline FE development (no backend).
 *
 * Mirrors the shape the real API will serve:
 *   GET /api/replay/sessions  -> ReplaySession[]
 *   GET /api/replay           -> Snapshot[] (a minute range)
 *
 * Frames are generated deterministically (no Math.random) by evolving the base
 * mock snapshot's field over the session minutes, and each frame is validated
 * via parseSnapshot so any drift from the contract fails fast.
 */
import { parseSnapshot, type Instrument, type Snapshot } from "@flowdesk/contracts";
import { MOCK_SNAPSHOTS } from "./mock-data";

/** One available replay session (PRD #10 / API 2.3). */
export interface ReplaySession {
  session_date: string;
  minute_count: number;
}

/** RTH is 09:30–16:00 ET = 390 minutes (minute_index 0..389). */
export const RTH_MINUTES = 390;

/** Mock list of available sessions per instrument (most-recent first). */
export const MOCK_SESSIONS: Record<Instrument, ReplaySession[]> = {
  ES: [
    { session_date: "2026-06-10", minute_count: RTH_MINUTES },
    { session_date: "2026-06-09", minute_count: RTH_MINUTES },
    { session_date: "2026-06-08", minute_count: RTH_MINUTES },
  ],
  NQ: [
    { session_date: "2026-06-10", minute_count: RTH_MINUTES },
    { session_date: "2026-06-09", minute_count: RTH_MINUTES },
  ],
};

/** ET minute_index 0 = 09:30; build the UTC ts for a given minute (EDT = UTC-4). */
function tsForMinute(sessionDate: string, minuteIndex: number): string {
  // 09:30 ET == 13:30 UTC during EDT. Add minuteIndex minutes.
  const base = Date.parse(`${sessionDate}T13:30:00Z`);
  const d = new Date(base + minuteIndex * 60_000);
  return d.toISOString().replace(/\.\d{3}Z$/, "Z");
}

/**
 * Build a single replay frame for (instrument, session, minuteIndex) by
 * drifting the base mock field with a slow time-varying phase. Deterministic.
 */
function buildFrame(
  instrument: Instrument,
  sessionDate: string,
  minuteIndex: number,
): Snapshot {
  const base = MOCK_SNAPSHOTS[instrument];
  const phase = Math.sin((minuteIndex / RTH_MINUTES) * Math.PI); // 0..1..0 over the day
  const drift = 0.6 + 0.4 * phase;

  const gamma = base.field.gamma.map((g) => Math.round(g * drift));
  const delta = base.field.delta.map((d) => Math.round(d * (1.2 - 0.4 * phase)));
  const profile = base.profile.map((r) => ({
    strike: r.strike,
    net_gex: Math.round(r.net_gex * drift),
    net_dex: Math.round(r.net_dex * (1.2 - 0.4 * phase)),
    interpolated: r.interpolated,
  }));

  const netGamma = Math.round(base.regime.net_gamma * drift);
  const sign = netGamma > 0 ? 1 : netGamma < 0 ? -1 : 0;
  // Stability rises toward midday (more pinning), falls at the open/close.
  const stability = Math.round((30 + 50 * phase) * 10) / 10;

  return parseSnapshot({
    ...base,
    session_date: sessionDate,
    ts: tsForMinute(sessionDate, minuteIndex),
    minute_index: minuteIndex,
    // Recorded frames carry their original session state (LIVE). REPLAY is a
    // frontend *mode* (store/connectionState), not a snapshot state — the
    // contract enum is PREMARKET|LIVE|STALE|CLOSED|HOLIDAY.
    state: "LIVE",
    stale: false,
    expired: false,
    regime: { net_gamma: netGamma, sign, stability_pct: stability },
    profile,
    field: { price_grid: base.field.price_grid, gamma, delta },
  });
}

/**
 * Mock of GET /api/replay: return the inclusive [from, to] minute frames for a
 * session. Clamped to the RTH range.
 */
export function getReplayRange(
  instrument: Instrument,
  sessionDate: string,
  fromMinute: number,
  toMinute: number,
): Snapshot[] {
  const lo = Math.max(0, Math.min(fromMinute, RTH_MINUTES - 1));
  const hi = Math.max(lo, Math.min(toMinute, RTH_MINUTES - 1));
  const frames: Snapshot[] = [];
  for (let m = lo; m <= hi; m++) frames.push(buildFrame(instrument, sessionDate, m));
  return frames;
}

/** Convenience: a full session's frames (used to seed the scrubber offline). */
export function getFullSession(instrument: Instrument, sessionDate: string): Snapshot[] {
  return getReplayRange(instrument, sessionDate, 0, RTH_MINUTES - 1);
}
