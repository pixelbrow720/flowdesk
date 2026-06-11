"use client";

import { useEffect, useRef, useState } from "react";
import { useDashboardStore, type WallCount, type CandleSize } from "../../lib/store";
import { useAutoFade } from "../../lib/use-auto-fade";
import { Panel } from "../ui/panel";
import { Toggle } from "../ui/toggle";
import { SegmentedControl } from "../ui/segmented-control";
import { Divider } from "../ui/divider";
import { ThemeToggle } from "../theme-toggle";
import { cn } from "../../lib/cn";

export interface FloatingToolbarProps {
  className?: string;
}

const WALL_OPTS: { value: string; label: string }[] = [
  { value: "1", label: "TOP 1" },
  { value: "2", label: "TOP 2" },
  { value: "3", label: "TOP 3" },
];

/**
 * Floating glass toolbar overlaying the chart (PRD #4). Glassmorphism-lite,
 * auto-fades after 2.5s idle and reappears on pointer movement over the chart;
 * stays visible while hovered or focused. All controls are wired to the store
 * and the bar is keyboard accessible. Respects prefers-reduced-motion (no fade).
 *
 * Must be placed inside a `position: relative` chart container — it attaches a
 * pointermove listener to that positioned ancestor to wake on activity.
 */
export function FloatingToolbar({ className }: FloatingToolbarProps) {
  const profileMetric = useDashboardStore((s) => s.profileMetric);
  const setProfileMetric = useDashboardStore((s) => s.setProfileMetric);
  const heatmapBasis = useDashboardStore((s) => s.heatmapBasis);
  const setHeatmapBasis = useDashboardStore((s) => s.setHeatmapBasis);
  const heatmapSmooth = useDashboardStore((s) => s.heatmapSmooth);
  const setHeatmapSmooth = useDashboardStore((s) => s.setHeatmapSmooth);
  const wallCount = useDashboardStore((s) => s.wallCount);
  const setWallCount = useDashboardStore((s) => s.setWallCount);
  const zoomPts = useDashboardStore((s) => s.zoomPts);
  const setZoomPts = useDashboardStore((s) => s.setZoomPts);
  const candleSize = useDashboardStore((s) => s.candleSize);
  const setCandleSize = useDashboardStore((s) => s.setCandleSize);

  const rootRef = useRef<HTMLDivElement | null>(null);
  const [hold, setHold] = useState(false);
  const { visible, onPointerMove, show } = useAutoFade({ idleMs: 2500, hold });

  // Wake the toolbar on pointer movement anywhere over its positioned ancestor.
  useEffect(() => {
    const el = rootRef.current;
    const parent = el?.offsetParent as HTMLElement | null;
    if (!parent) return;
    parent.addEventListener("pointermove", onPointerMove);
    return () => parent.removeEventListener("pointermove", onPointerMove);
  }, [onPointerMove]);

  return (
    <div
      ref={rootRef}
      className={cn(
        "pointer-events-none absolute bottom-16 left-1/2 z-30 -translate-x-1/2",
        className,
      )}
    >
      <Panel
        variant="glass"
        role="toolbar"
        aria-label="Chart controls"
        onMouseEnter={() => setHold(true)}
        onMouseLeave={() => setHold(false)}
        onFocusCapture={() => {
          setHold(true);
          show();
        }}
        onBlurCapture={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node)) setHold(false);
        }}
        className={cn(
          "pointer-events-auto flex items-center gap-12 px-12 py-8 shadow-elevation-2",
          "transition-opacity duration-slow ease-standard",
          visible ? "opacity-100" : "opacity-0",
        )}
      >
        <ToolbarGroup label="Metric">
          <SegmentedControl
            ariaLabel="Profile metric"
            value={profileMetric}
            onChange={setProfileMetric}
            options={[
              { value: "GEX", label: "GEX" },
              { value: "DEX", label: "DEX" },
            ]}
          />
        </ToolbarGroup>

        <Divider orientation="vertical" className="h-24" />

        <ToolbarGroup label="Basis">
          <SegmentedControl
            ariaLabel="Heatmap basis"
            value={heatmapBasis}
            onChange={setHeatmapBasis}
            options={[
              { value: "GAMMA", label: "GAMMA" },
              { value: "DELTA", label: "DELTA" },
            ]}
          />
        </ToolbarGroup>

        <Divider orientation="vertical" className="h-24" />

        <ToolbarGroup label="Render">
          <Toggle
            checked={heatmapSmooth}
            onChange={setHeatmapSmooth}
            label={heatmapSmooth ? "Smooth" : "Block"}
          />
        </ToolbarGroup>

        <Divider orientation="vertical" className="h-24" />

        <ToolbarGroup label="Candle">
          <SegmentedControl
            ariaLabel="Candle size"
            value={String(candleSize)}
            onChange={(v) => setCandleSize(Number(v) as CandleSize)}
            options={[
              { value: "1", label: "1m" },
              { value: "5", label: "5m" },
            ]}
          />
        </ToolbarGroup>

        <Divider orientation="vertical" className="h-24" />

        <ToolbarGroup label="Walls">
          <SegmentedControl
            ariaLabel="Key levels wall count"
            value={String(wallCount)}
            onChange={(v) => setWallCount(Number(v) as WallCount)}
            options={WALL_OPTS}
          />
        </ToolbarGroup>

        <Divider orientation="vertical" className="h-24" />

        <ToolbarGroup label="Zoom">
          <div className="flex items-center gap-4">
            <button
              type="button"
              aria-label="Zoom out (show more strikes)"
              onClick={() => setZoomPts(zoomPts + 10)}
              className="flex h-20 w-20 items-center justify-center rounded-sm border border-border font-mono text-fg hover:bg-surface"
            >
              −
            </button>
            <span className="min-w-[44px] text-center font-mono text-[11px] tabular-nums text-fg">
              ±{zoomPts}
            </span>
            <button
              type="button"
              aria-label="Zoom in (show fewer strikes)"
              onClick={() => setZoomPts(zoomPts - 10)}
              className="flex h-20 w-20 items-center justify-center rounded-sm border border-border font-mono text-fg hover:bg-surface"
            >
              +
            </button>
          </div>
        </ToolbarGroup>

        <Divider orientation="vertical" className="h-24" />

        <ToolbarGroup label="Theme">
          <ThemeToggle />
        </ToolbarGroup>
      </Panel>
    </div>
  );
}

function ToolbarGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-4">
      <span className="font-display text-[10px] uppercase tracking-[0.08em] text-muted">
        {label}
      </span>
      {children}
    </div>
  );
}
