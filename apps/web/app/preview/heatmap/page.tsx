"use client";

import { useDashboardStore } from "../../../lib/store";
import { ThemeToggle } from "../../../components/theme-toggle";
import { SegmentedControl } from "../../../components/ui/segmented-control";
import { Pill } from "../../../components/ui/pill";
import { Heatmap } from "../../../components/heatmap";

/** Standalone preview for the 4.2 WebGL heatmap centerpiece. */
export default function HeatmapPreviewPage() {
  const instrument = useDashboardStore((s) => s.instrument);
  const setInstrument = useDashboardStore((s) => s.setInstrument);
  const snapshot = useDashboardStore((s) => s.snapshot);

  return (
    <main className="flex h-screen flex-col gap-16 p-24">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-16">
          <h1 className="font-display text-h2 text-fg">
            Flow<span className="text-turquoise">Desk</span> · Heatmap
          </h1>
          <SegmentedControl
            ariaLabel="Instrument"
            value={instrument}
            onChange={setInstrument}
            options={[
              { value: "ES", label: "ES" },
              { value: "NQ", label: "NQ" },
            ]}
          />
          <Pill tone={snapshot.regime.sign >= 0 ? "positive" : "negative"} glow>
            {snapshot.regime.sign >= 0 ? "PINNING" : "VOLATILE"}
          </Pill>
        </div>
        <ThemeToggle />
      </header>

      <div className="min-h-0 flex-1">
        <Heatmap />
      </div>
    </main>
  );
}
