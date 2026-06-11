"use client";

import { useState } from "react";
import { useDashboardStore } from "../../../lib/store";
import { useRealtime, type RealtimeSource } from "../../../lib/use-realtime";
import { usePrefs } from "../../../lib/use-prefs";
import { DEFAULT_ME } from "../../../lib/me-mock";
import { Topbar, RegimeBar, KeyLevelsBar } from "../../../components/topbar";
import { ThemeToggle } from "../../../components/theme-toggle";
import { SegmentedControl } from "../../../components/ui/segmented-control";
import { Pill } from "../../../components/ui/pill";
import { ChartLayout } from "../../../components/chart";
import { FloatingToolbar } from "../../../components/toolbar";
import { Scrubber } from "../../../components/scrubber";
import { SettingsPanel } from "../../../components/settings";

/**
 * Standalone preview of the assembled dashboard: topbar (4.4), chart (4.3) +
 * floating toolbar (4.5), scrubber (4.6), realtime feed (4.7), and the Settings
 * slide-in (4.8) opened from the topbar gear. Prefs persist via flowdesk.prefs.
 */
export default function DashboardPreviewPage() {
  const [source, setSource] = useState<RealtimeSource>("mock");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const stale = useDashboardStore((s) => s.stale);
  const authError = useDashboardStore((s) => s.authError);
  const mode = useDashboardStore((s) => s.mode);

  usePrefs();
  useRealtime({ source, intervalMs: 700, staleAfter: 8 });

  return (
    <main className="flex h-screen flex-col">
      <Topbar onOpenSettings={() => setSettingsOpen(true)} />
      <KeyLevelsBar />

      {/* Dev strip: realtime source toggle + status pills + regime bar. */}
      <div className="flex items-center gap-16 border-b border-border px-12 py-8">
        <span className="font-display text-[10px] uppercase tracking-[0.08em] text-muted">
          Feed
        </span>
        <SegmentedControl
          ariaLabel="Realtime source"
          value={source}
          onChange={setSource}
          options={[
            { value: "mock", label: "MOCK" },
            { value: "live", label: "LIVE WS" },
          ]}
        />
        {mode === "LIVE" && stale && (
          <Pill tone="negative" glow>
            STALE — holding last frame
          </Pill>
        )}
        {authError && (
          <Pill tone="negative">
            {authError === "RELOGIN" ? "Session expired" : "DESK required"}
          </Pill>
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

      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        me={DEFAULT_ME}
      />
    </main>
  );
}
