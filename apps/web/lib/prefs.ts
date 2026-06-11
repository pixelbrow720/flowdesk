/**
 * User preferences, persisted to localStorage under a single key
 * `flowdesk.prefs` (PRD #5). v1: client-only, no server sync. The schema is
 * versioned so a future shape change can migrate or reset cleanly.
 *
 * Defaults (PRD #5): theme Dark, profile metric Net GEX, heatmap basis Gamma,
 * smooth render, default instrument ES, timezone display ET.
 */
import type { Instrument } from "@flowdesk/contracts";
import type { HeatmapBasis, ProfileMetric } from "./store";
import type { Theme } from "../components/theme-provider";

export const PREFS_KEY = "flowdesk.prefs";
export const PREFS_VERSION = 1 as const;

export interface Prefs {
  version: typeof PREFS_VERSION;
  theme: Theme;
  profileMetric: ProfileMetric;
  heatmapBasis: HeatmapBasis;
  heatmapSmooth: boolean;
  instrument: Instrument;
  /** Display timezone. v1 is ET-only (locked session tz); kept for forward-compat. */
  timezone: "ET";
}

export const DEFAULT_PREFS: Prefs = {
  version: PREFS_VERSION,
  theme: "dark",
  profileMetric: "GEX",
  heatmapBasis: "GAMMA",
  heatmapSmooth: true,
  instrument: "ES",
  timezone: "ET",
};

function isTheme(v: unknown): v is Theme {
  return v === "dark" || v === "light";
}
function isMetric(v: unknown): v is ProfileMetric {
  return v === "GEX" || v === "DEX";
}
function isBasis(v: unknown): v is HeatmapBasis {
  return v === "GAMMA" || v === "DELTA";
}
function isInstrument(v: unknown): v is Instrument {
  return v === "ES" || v === "NQ";
}

/**
 * Read + validate prefs from localStorage, falling back to defaults for any
 * missing/invalid field. Never throws (SSR-safe: returns defaults when there is
 * no window).
 */
export function readPrefs(): Prefs {
  if (typeof window === "undefined") return { ...DEFAULT_PREFS };
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(PREFS_KEY);
  } catch {
    return { ...DEFAULT_PREFS };
  }
  if (!raw) return { ...DEFAULT_PREFS };

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { ...DEFAULT_PREFS };
  }
  if (typeof parsed !== "object" || parsed === null) return { ...DEFAULT_PREFS };
  const p = parsed as Record<string, unknown>;

  return {
    version: PREFS_VERSION,
    theme: isTheme(p.theme) ? p.theme : DEFAULT_PREFS.theme,
    profileMetric: isMetric(p.profileMetric) ? p.profileMetric : DEFAULT_PREFS.profileMetric,
    heatmapBasis: isBasis(p.heatmapBasis) ? p.heatmapBasis : DEFAULT_PREFS.heatmapBasis,
    heatmapSmooth:
      typeof p.heatmapSmooth === "boolean" ? p.heatmapSmooth : DEFAULT_PREFS.heatmapSmooth,
    instrument: isInstrument(p.instrument) ? p.instrument : DEFAULT_PREFS.instrument,
    timezone: "ET",
  };
}

/** Persist prefs (best-effort; ignores storage errors / SSR). */
export function writePrefs(prefs: Prefs): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* storage full / disabled — non-fatal */
  }
}
