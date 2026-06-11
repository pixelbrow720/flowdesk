"use client";

import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { useDashboardStore } from "../../lib/store";
import { makeWindowedYScale } from "../../lib/scale";
import { Heatmap } from "../heatmap";
import { ProfileLine } from "./profile-line";
import { SharedAxis } from "./shared-axis";

export interface ChartLayoutProps {
  /** Profile panel width fraction (locked ~22%). */
  profileFraction?: number;
  /** Axis column width in px (locked ~72px). */
  axisWidth?: number;
  className?: string;
}

/**
 * The locked dashboard chart layout (PRD #4): a single full-width row split
 * into LEFT profile line (~22%), the CENTERED shared strike axis (~72px), and
 * the RIGHT heatmap (remaining width). All three share ONE windowed Y-scale +
 * strike grid (±zoomPts around the zero-gamma / gamma-flip level, driven by the
 * store's vertical zoom control), so the profile rows, axis ticks, and heatmap
 * rows are aligned AND focused on the money.
 */
export function ChartLayout({
  profileFraction = 0.22,
  axisWidth = 72,
  className,
}: ChartLayoutProps) {
  const snapshot = useDashboardStore((s) => s.snapshot);
  const metric = useDashboardStore((s) => s.profileMetric);
  const zoomPts = useDashboardStore((s) => s.zoomPts);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      setSize({ width: r.width, height: r.height });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const profileWidth = Math.max(0, Math.round(size.width * profileFraction));
  const heatmapWidth = Math.max(0, size.width - profileWidth - axisWidth);

  // Window both panels to +/- windowPts around zero gamma (gamma flip), falling
  // back to the forward when no flip is present.
  const center = snapshot.levels.gamma_flip ?? snapshot.forward;
  const scale = useMemo(
    () => makeWindowedYScale(center, zoomPts, snapshot.axis.step, size.height),
    [center, zoomPts, snapshot.axis.step, size.height],
  );
  // The shared strike grid both panels sample onto.
  const targetGrid = useMemo(() => scale.ticks(), [scale]);

  return (
    <div
      ref={containerRef}
      className={`flex h-full w-full overflow-hidden ${className ?? ""}`}
    >
      {/* LEFT: profile line */}
      <div className="shrink-0 border-r border-border" style={{ width: profileWidth }}>
        {size.height > 0 && (
          <ProfileLine
            profile={snapshot.profile}
            metric={metric}
            scale={scale}
            width={profileWidth}
          />
        )}
      </div>

      {/* CENTER: shared strike axis */}
      <div className="shrink-0" style={{ width: axisWidth }}>
        {size.height > 0 && (
          <SharedAxis scale={scale} forward={snapshot.forward} width={axisWidth} />
        )}
      </div>

      {/* RIGHT: heatmap (fills remaining width). Shares the windowed strike grid
          so its rows align with the profile + axis sign-for-sign. */}
      <div className="min-w-0 flex-1" style={{ width: heatmapWidth }}>
        <Heatmap showControls={false} priceGrid={targetGrid} />
      </div>
    </div>
  );
}
