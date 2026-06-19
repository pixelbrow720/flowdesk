"use client";

/**
 * ArcHeatmap — top-down gamma-density heatmap (Canvas2D).
 *
 * The left panel of the Arc section: a price × session-time heatmap of the
 * engine's `fog.gamma` field. X-axis = forward price grid, Y-axis = session
 * minute (time flows DOWN, newest at the bottom). Cell color is the diverging
 * gamma scale (crimson short-gamma → bone zero → turquoise long-gamma). A thin
 * crimson playhead line marks the current minute so it stays in sync with the
 * 3D surface on the right.
 *
 * Pure render: all data shaping is in `arcHeatmap.ts` (unit-tested); this
 * component only paints the grid to a canvas and handles resize.
 */

import { useEffect, useMemo, useRef } from "react";
import { buildHeatmap, gammaToColor, type HeatmapFrame } from "./arcHeatmap";

export interface ArcHeatmapProps {
  frames: HeatmapFrame[];
  /** Playhead minute_index for the "now" line. -1 hides it. */
  playheadMinute: number;
  className?: string;
}

export function ArcHeatmap({
  frames,
  playheadMinute,
  className = "flex-1",
}: ArcHeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const heatmap = useMemo(() => buildHeatmap(frames), [frames]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;

    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = parent.clientWidth;
      const h = parent.clientHeight;
      canvas.width = Math.max(1, Math.floor(w * dpr));
      canvas.height = Math.max(1, Math.floor(h * dpr));
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#000000";
      ctx.fillRect(0, 0, w, h);

      const { prices, minutes, grid, range } = heatmap;
      const nCols = prices.length;
      const nRows = minutes.length;
      if (nCols === 0 || nRows === 0) {
        ctx.fillStyle = "#6B655B";
        ctx.font = "11px ui-monospace, monospace";
        ctx.fillText("awaiting fog field…", 12, 20);
        return;
      }

      // Leave a small left gutter for price labels.
      const padL = 44;
      const padB = 16;
      const plotW = Math.max(1, w - padL);
      const plotH = Math.max(1, h - padB);
      const cellW = plotW / nCols;
      const cellH = plotH / nRows;

      // Rows: time flows DOWN (row 0 = earliest at top, last = newest at bottom).
      for (let r = 0; r < nRows; r++) {
        for (let c = 0; c < nCols; c++) {
          const col = gammaToColor(grid[r][c], range);
          ctx.fillStyle = `rgb(${col.r | 0}, ${col.g | 0}, ${col.b | 0})`;
          ctx.fillRect(
            padL + c * cellW,
            r * cellH,
            Math.ceil(cellW) + 0.5,
            Math.ceil(cellH) + 0.5,
          );
        }
      }

      // Playhead line at the current minute (interpolated to its row).
      if (playheadMinute >= 0) {
        // Find the row whose minute is closest to (and <=) the playhead.
        let row = -1;
        for (let r = 0; r < nRows; r++) {
          if (minutes[r] <= playheadMinute) row = r;
        }
        if (row >= 0) {
          const y = (row + 1) * cellH;
          ctx.strokeStyle = "#B5002E";
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(padL, y);
          ctx.lineTo(w, y);
          ctx.stroke();
        }
      }

      // Price axis labels (min / mid / max).
      ctx.fillStyle = "#8E8E88";
      ctx.font = "9px ui-monospace, monospace";
      const labelPrices = [prices[0], prices[Math.floor(nCols / 2)], prices[nCols - 1]];
      ctx.fillText(`${labelPrices[0].toFixed(0)}`, 2, plotH - 2);
      ctx.fillText(`${labelPrices[2].toFixed(0)}`, 2, 10);
    };

    draw();
    const ro = new ResizeObserver(draw);
    ro.observe(parent);
    return () => ro.disconnect();
  }, [heatmap, playheadMinute]);

  return (
    <div className={`relative min-w-0 ${className}`}>
      <div className="relative min-h-[560px] flex-1 overflow-hidden rounded-[4px] border border-rule/40 bg-black">
        <canvas ref={canvasRef} className="block h-full w-full" />
      </div>
    </div>
  );
}
