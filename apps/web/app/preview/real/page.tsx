"use client";

import { useEffect } from "react";
import { useDashboardStore } from "../../../lib/store";
import { useSessionLoader, REAL_SESSIONS } from "../../../lib/session-loader";
import { usePrefs } from "../../../lib/use-prefs";
import { Topbar, RegimeBar, KeyLevelsBar } from "../../../components/topbar";
import { ThemeToggle } from "../../../components/theme-toggle";
import { SegmentedControl } from "../../../components/ui/segmented-control";
import { Spinner } from "../../../components/ui/spinner";
import { Pill } from "../../../components/ui/pill";
import { ChartLayout } from "../../../components/chart";
import { FloatingToolbar } from "../../../components/toolbar";
import { Scrubber } from "../../../components/scrubber";

/**
 * REAL DATA preview: loads a captured ES/NQ session (from Databento, generated
 * by scripts/gen_session_snapshots.py and served from /public/sessions) into
 * the store as REPLAY frames. Scrub/play the scrubber to move through the real
 * 390-minute session; the heatmap, profile, regime, and levels are all real.
 */
export default function RealDataPreviewPage() {
  const { status, error, load } = useSessionLoader();
  const instrument = useDashboardStore((s) => s.instrument);
  const replayDate = useDashboardStore((s) => s.replayDate);
  const frames = useDashboardStore((s) => s.frames);
  const setFrameIndex = useDashboardStore((s) => s.setFrameIndex);

  usePrefs();

  // Load the ES session on mount.
  useEffect(() => {
    void load("ES", "2026-06-09");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Land on a data-rich midday frame after a session loads: at the 09:30 open
  // cumulative volume is ~0, so the VOL-based field is empty (flat profile,
  // uniform heatmap). Jumping to midday shows real structure immediately; the
  // user can still scrub back to the open.
  useEffect(() => {
    if (frames.length > 0) setFrameIndex(Math.floor(frames.length / 2));
  }, [frames, setFrameIndex]);

  return (
    <main className="flex h-screen flex-col">
      <Topbar />
      <KeyLevelsBar />

      <div className="flex items-center gap-16 border-b border-border px-12 py-8">
        <span className="font-display text-[10px] uppercase tracking-[0.08em] text-muted">
          Real session
        </span>
        <SegmentedControl
          ariaLabel="Load session"
          value={instrument}
          onChange={(v) =>
            void load(
              v,
              REAL_SESSIONS.find((s) => s.instrument === v)?.date ?? "2026-06-09",
            )
          }
          options={REAL_SESSIONS.map((s) => ({ value: s.instrument, label: s.instrument }))}
        />
        {status === "loading" && (
          <span className="flex items-center gap-8 text-muted">
            <Spinner size="sm" />
            <span className="font-display text-caption">memuat sesi…</span>
          </span>
        )}
        {status === "loaded" && (
          <Pill tone="positive">
            {instrument} {replayDate} · {frames.length} menit (real)
          </Pill>
        )}
        {status === "error" && (
          <Pill tone="negative">gagal memuat: {error}</Pill>
        )}
        <RegimeBar />
        <span className="ml-auto">
          <ThemeToggle />
        </span>
      </div>

      <div className="min-h-0 flex-1 p-12">
        <div className="relative h-full overflow-hidden rounded-lg border border-border">
          <ChartLayout />
          <FloatingToolbar />
        </div>
      </div>

      <Scrubber />
    </main>
  );
}
