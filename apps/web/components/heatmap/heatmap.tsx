"use client";

import { useMemo } from "react";
import { useDashboardStore, type CandleSize } from "../../lib/store";
import { useTheme } from "../theme-provider";
import { SegmentedControl } from "../ui/segmented-control";
import { Toggle } from "../ui/toggle";
import { HeatmapCanvas } from "./heatmap-canvas";
import { HeatmapOverlay } from "./heatmap-overlay";
import { Colorbar } from "./colorbar";
import { buildReplayField2D } from "../../lib/heatmap/field-2d";

export interface HeatmapProps {
  /** Shared windowed strike grid from the chart layout (rows align with profile). */
  priceGrid?: number[];
  /** Show the inline candle + smooth toggles (standalone/preview use). */
  showControls?: boolean;
  className?: string;
}

// Locked ramp ends; mid anchor swaps with theme (black<->white).
const LOW = "#40E0D0";
const HIGH = "#E0183C";

/**
 * Heatmap centerpiece: WebGL2 topografi surface + OKLab colorbar. Driven by the
 * SAME profile metric (Net GEX / Net DEX) as the left profile panel, so the two
 * agree sign-for-sign. Columns are candles (1 or 5 min). Smooth filtering turns
 * the binned field into the continuous topografi surface.
 */
export function Heatmap({ priceGrid, showControls = true, className }: HeatmapProps) {
  const snapshot = useDashboardStore((s) => s.snapshot);
  const profileMetric = useDashboardStore((s) => s.profileMetric);
  const smooth = useDashboardStore((s) => s.heatmapSmooth);
  const setSmooth = useDashboardStore((s) => s.setHeatmapSmooth);
  const candleSize = useDashboardStore((s) => s.candleSize);
  const setCandleSize = useDashboardStore((s) => s.setCandleSize);
  const mode = useDashboardStore((s) => s.mode);
  const frames = useDashboardStore((s) => s.frames);
  const frameIndex = useDashboardStore((s) => s.frameIndex);
  const { theme } = useTheme();

  const heatMetric = profileMetric === "GEX" ? "net_gex" : "net_dex";
  // Strike grid: the shared windowed grid when embedded, else the snapshot's own.
  const grid = priceGrid ?? snapshot.field.price_grid;

  const field = useMemo(() => {
    // REPLAY: candle-bin the real minute frames up to the scrubber position.
    // Otherwise (LIVE/mock) treat the current snapshot as the single latest candle.
    const src = mode === "REPLAY" && frames.length > 0 ? frames : [snapshot];
    const upTo = mode === "REPLAY" && frames.length > 0 ? frameIndex : 0;
    return buildReplayField2D(src, upTo, heatMetric, grid, candleSize);
  }, [snapshot, heatMetric, grid, candleSize, mode, frames, frameIndex]);

  const stops = useMemo(
    () => ({ low: LOW, mid: theme === "light" ? "#FFFFFF" : "#000000", high: HIGH }),
    [theme],
  );

  return (
    <div className={`flex h-full w-full flex-col gap-12 ${className ?? ""}`}>
      {showControls && (
        <div className="flex items-center gap-16">
          <SegmentedControl
            ariaLabel="Profile metric"
            value={profileMetric}
            onChange={useDashboardStore.getState().setProfileMetric}
            options={[
              { value: "GEX", label: "NET GEX" },
              { value: "DEX", label: "NET DEX" },
            ]}
          />
          <SegmentedControl
            ariaLabel="Candle size"
            value={String(candleSize)}
            onChange={(v) => setCandleSize(Number(v) as CandleSize)}
            options={[
              { value: "1", label: "1m" },
              { value: "5", label: "5m" },
            ]}
          />
          <Toggle
            checked={smooth}
            onChange={setSmooth}
            label={smooth ? "Smooth" : "Block"}
          />
        </div>
      )}
      <div className="flex min-h-0 flex-1 gap-16">
        <div className="relative min-h-0 flex-1 overflow-hidden rounded-lg border border-border">
          <HeatmapCanvas field={field} stops={stops} block={!smooth} />
          <HeatmapOverlay priceGrid={field.priceGrid} />
        </div>
        <Colorbar
          basis={profileMetric === "GEX" ? "GAMMA" : "DELTA"}
          theme={theme}
          maxAbs={field.maxAbs}
        />
      </div>
    </div>
  );
}
