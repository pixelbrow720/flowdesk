"use client";

/**
 * ArcGammaTable — left-panel gamma-density TABLE renderer.
 *
 * Strike × minute grid (HTML <table>, no Canvas) so cells render crisp at any
 * zoom. Each cell shows the formatted gamma value (compact $-notational)
 * with a diverging background (crimson short-gamma → bone zero → turquoise
 * long-gamma). The minute axis is sampled to ~14 rows so the table stays
 * readable; the FULL strike axis is rendered and scrolls horizontally (the
 * sticky min column + sticky header row keep the axes pinned while scrolling).
 * A thin crimson playhead row marks the latest minute so the table stays in
 * sync with the 3D surface on the right.
 *
 * The pure grid/shape math lives in `arcHeatmap.ts` (unit-tested). This file
 * only paints the table.
 */

import { useMemo } from "react";
import {
  buildHeatmap,
  formatGamma,
  gammaToColor,
  sampleRows,
  type HeatmapFrame,
} from "./arcHeatmap";

export interface ArcGammaTableProps {
  frames: HeatmapFrame[];
  /** Playhead minute_index for the "now" row marker. -1 hides it. */
  playheadMinute: number;
  /** Cap on minute rows displayed (default 14). */
  maxMinuteRows?: number;
  className?: string;
}

export function ArcGammaTable({
  frames,
  playheadMinute,
  maxMinuteRows = 14,
  className = "flex-1",
}: ArcGammaTableProps) {
  const heatmap = useMemo(() => buildHeatmap(frames), [frames]);

  const { sampledMinutes, sampledGrid, visiblePrices } = useMemo(() => {
    if (heatmap.prices.length === 0) {
      return {
        sampledMinutes: [] as number[],
        sampledGrid: [] as (number | null)[][],
        visiblePrices: [] as number[],
      };
    }
    const rows = sampleRows(heatmap.minutes, maxMinuteRows);
    const minuteToRow = new Map<number, number>();
    heatmap.minutes.forEach((m, i) => minuteToRow.set(m, i));
    const sampledGrid = rows.map((m) => heatmap.grid[minuteToRow.get(m) ?? 0]);
    // Render the FULL strike axis — the panel scrolls horizontally rather than
    // truncating, so no information is hidden (user spec 2026-06-19).
    return {
      sampledMinutes: rows,
      sampledGrid,
      visiblePrices: heatmap.prices,
    };
  }, [heatmap, maxMinuteRows]);

  const { range } = heatmap;
  const latestMinute = sampledMinutes[sampledMinutes.length - 1];

  return (
    <div className={`relative min-w-0 ${className}`}>
      <div className="heatmap-scroll absolute inset-0 flex flex-col overflow-auto overscroll-contain rounded-[3px] border border-rule/40 bg-black">
        {sampledMinutes.length === 0 ? (
          <div className="flex flex-1 items-center justify-center font-mono text-[11px] tracking-[0.2em] text-bone-3/60">
            awaiting fog field…
          </div>
        ) : (
          <table className="border-collapse whitespace-nowrap font-mono text-[9px] tabular-nums">
            <thead className="sticky top-0 z-10 bg-black">
              <tr>
                <th className="sticky left-0 z-20 bg-black px-2 py-1.5 text-left font-normal uppercase tracking-[0.18em] text-bone-3">
                  min
                </th>
                {visiblePrices.map((p) => (
                  <th
                    key={p}
                    className="border-l border-rule/30 px-1.5 py-1.5 text-right font-normal text-bone-3"
                  >
                    {p.toFixed(0)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sampledMinutes.map((m, r) => {
                const isPlayhead = m === latestMinute && playheadMinute >= 0;
                return (
                  <tr
                    key={m}
                    className={isPlayhead ? "ring-1 ring-inset ring-[#B5002E]" : ""}
                  >
                    <th
                      scope="row"
                      className="sticky left-0 z-10 border-t border-rule/30 bg-black px-2 py-1 text-left font-normal text-bone-3"
                    >
                      {m}
                    </th>
                    {visiblePrices.map((p, c) => {
                      const v = sampledGrid[r]?.[c] ?? null;
                      const col = gammaToColor(v, range);
                      const lum =
                        (col.r * 0.299 + col.g * 0.587 + col.b * 0.114) / 255;
                      const text = lum < 0.55 ? "#FAFAF7" : "#1A1A1F";
                      return (
                        <td
                          key={p}
                          className="border-l border-t border-rule/30 px-1.5 py-1 text-right"
                          style={{
                            backgroundColor: `rgb(${col.r | 0}, ${col.g | 0}, ${col.b | 0})`,
                            color: text,
                          }}
                          title={
                            v === null
                              ? `no fog data at min ${m}, $${p}`
                              : `γ ${formatGamma(v)} at min ${m}, $${p}`
                          }
                        >
                          {formatGamma(v)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}