"use client";

import { useEffect, useRef } from "react";
import { useDashboardStore } from "./store";
import { useTheme } from "../components/theme-provider";
import { DEFAULT_PREFS, readPrefs, writePrefs, type Prefs } from "./prefs";

/**
 * Bridge between persisted prefs (`flowdesk.prefs`) and live state.
 *
 * On mount: read prefs and hydrate the store (instrument/metric/basis/smooth)
 * + the theme provider. While mounted: persist whenever any pref-backed value
 * changes. v1 is client-only (PRD #5: no server presets).
 *
 * Mount this once near the dashboard root.
 */
export function usePrefs(): void {
  const { theme, setTheme } = useTheme();
  const hydrated = useRef(false);

  const instrument = useDashboardStore((s) => s.instrument);
  const profileMetric = useDashboardStore((s) => s.profileMetric);
  const heatmapBasis = useDashboardStore((s) => s.heatmapBasis);
  const heatmapSmooth = useDashboardStore((s) => s.heatmapSmooth);

  // Hydrate once on mount.
  useEffect(() => {
    const p = readPrefs();
    const s = useDashboardStore.getState();
    if (p.instrument !== s.instrument) s.setInstrument(p.instrument);
    s.setProfileMetric(p.profileMetric);
    s.setHeatmapBasis(p.heatmapBasis);
    s.setHeatmapSmooth(p.heatmapSmooth);
    setTheme(p.theme);
    hydrated.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist on any change (after the initial hydrate, so we don't clobber).
  useEffect(() => {
    if (!hydrated.current) return;
    const next: Prefs = {
      ...DEFAULT_PREFS,
      theme,
      profileMetric,
      heatmapBasis,
      heatmapSmooth,
      instrument,
    };
    writePrefs(next);
  }, [theme, profileMetric, heatmapBasis, heatmapSmooth, instrument]);
}
