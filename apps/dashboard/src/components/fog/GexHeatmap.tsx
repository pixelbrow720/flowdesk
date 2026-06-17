"use client";

import { useEffect, useRef, useState } from "react";

// FlowDesk brand colors
const TURQUOISE = { r: 15, g: 181, b: 168 }; // #0FB5A8
const CRIMSON = { r: 181, g: 0, b: 46 }; // #B5002E

export interface HeatmapFrame {
  ts: number; // epoch seconds
  forward: number;
  minute_index: number;
  price_grid: number[];
  gamma: number[];
  delta: number[];
}

interface GexHeatmapProps {
  frames: HeatmapFrame[];
  metric: "gamma" | "delta";
  tick?: number;
  onPriceAxisReady?: (axis: { min: number; max: number; levels: number[] }) => void;
}

// Build shared price axis from all frames
function buildSharedAxis(frames: HeatmapFrame[], tick: number) {
  let min = Infinity;
  let max = -Infinity;
  for (const f of frames) {
    if (f.price_grid.length > 0) {
      min = Math.min(min, f.price_grid[0]);
      max = Math.max(max, f.price_grid[f.price_grid.length - 1]);
    }
  }
  // Snap to tick boundaries
  min = Math.floor(min / tick) * tick;
  max = Math.ceil(max / tick) * tick;
  
  const levels: number[] = [];
  for (let p = min; p <= max; p += tick) {
    levels.push(p);
  }
  return { min, max, levels };
}

// Resample frame metric onto shared axis (linear interpolation)
function resampleFrame(
  frame: HeatmapFrame,
  axisLevels: number[],
  metric: "gamma" | "delta"
): number[] {
  const result = new Array<number>(axisLevels.length);
  const src = metric === "gamma" ? frame.gamma : frame.delta;
  const srcPrices = frame.price_grid;
  
  for (let i = 0; i < axisLevels.length; i++) {
    const target = axisLevels[i];
    if (target < srcPrices[0] || target > srcPrices[srcPrices.length - 1]) {
      result[i] = NaN;
      continue;
    }
    
    // Binary search for bracket
    let lo = 0;
    let hi = srcPrices.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (srcPrices[mid] <= target) lo = mid;
      else hi = mid;
    }
    
    // Linear interpolation
    const p0 = srcPrices[lo];
    const p1 = srcPrices[hi];
    const t = (target - p0) / (p1 - p0);
    result[i] = src[lo] * (1 - t) + src[hi] * t;
  }
  return result;
}

// Gaussian smoothing (NaN-aware)
function gaussianSmooth(values: number[], sigma: number): number[] {
  if (sigma <= 0) return values;
  const result = new Array<number>(values.length);
  const radius = Math.ceil(sigma * 3);
  
  for (let i = 0; i < values.length; i++) {
    let sum = 0;
    let weight = 0;
    
    for (let j = Math.max(0, i - radius); j <= Math.min(values.length - 1, i + radius); j++) {
      if (isNaN(values[j])) continue;
      const dist = i - j;
      const w = Math.exp(-(dist * dist) / (2 * sigma * sigma));
      sum += values[j] * w;
      weight += w;
    }
    
    result[i] = weight > 0 ? sum / weight : NaN;
  }
  return result;
}

// Color map: black → turquoise (positive) / crimson (negative)
function colorForValue(v: number): [number, number, number, number] {
  if (isNaN(v)) return [0, 0, 0, 0]; // transparent
  
  const clamped = Math.max(-1, Math.min(1, v));
  const intensity = Math.pow(Math.abs(clamped), 0.7); // power curve for depth
  const alpha = Math.round(intensity * 255);
  
  if (clamped > 0) {
    // Turquoise
    return [
      Math.round(TURQUOISE.r * intensity),
      Math.round(TURQUOISE.g * intensity),
      Math.round(TURQUOISE.b * intensity),
      alpha,
    ];
  } else if (clamped < 0) {
    // Crimson
    return [
      Math.round(CRIMSON.r * intensity),
      Math.round(CRIMSON.g * intensity),
      Math.round(CRIMSON.b * intensity),
      alpha,
    ];
  }
  return [0, 0, 0, 0];
}

// Marching squares for contour lines
function marchingSquares(
  grid: number[][],
  threshold: number,
  cellW: number,
  cellH: number
): Array<[number, number, number, number]> {
  const segments: Array<[number, number, number, number]> = [];
  const nT = grid.length;
  const nP = grid[0].length;
  
  for (let t = 0; t < nT - 1; t++) {
    for (let p = 0; p < nP - 1; p++) {
      const v00 = grid[t][p];
      const v10 = grid[t + 1][p];
      const v01 = grid[t][p + 1];
      const v11 = grid[t + 1][p + 1];
      
      // Skip if any NaN
      if (isNaN(v00) || isNaN(v10) || isNaN(v01) || isNaN(v11)) continue;
      
      // Case index
      const idx =
        (v00 >= threshold ? 1 : 0) |
        (v10 >= threshold ? 2 : 0) |
        (v11 >= threshold ? 4 : 0) |
        (v01 >= threshold ? 8 : 0);
      
      if (idx === 0 || idx === 15) continue; // no crossing
      
      // Interpolation helpers
      const interp = (a: number, b: number) => {
        const t = (threshold - a) / (b - a);
        return t;
      };
      
      const x0 = t * cellW;
      const x1 = (t + 1) * cellW;
      const y0 = p * cellH;
      const y1 = (p + 1) * cellH;
      
      // 16 cases
      let segs: Array<[number, number, number, number]> = [];
      switch (idx) {
        case 1:
        case 14:
          segs = [[x0 + interp(v00, v10) * cellW, y0, x0, y0 + interp(v00, v01) * cellH]];
          break;
        case 2:
        case 13:
          segs = [[x1, y0 + interp(v10, v11) * cellH, x0 + interp(v00, v10) * cellW, y0]];
          break;
        case 3:
        case 12:
          segs = [[x0, y0 + interp(v00, v01) * cellH, x1, y0 + interp(v10, v11) * cellH]];
          break;
        case 4:
        case 11:
          segs = [[x1, y0 + interp(v10, v11) * cellH, x0 + interp(v01, v11) * cellW, y1]];
          break;
        case 5:
        case 10:
          segs = [
            [x0 + interp(v00, v10) * cellW, y0, x1, y0 + interp(v10, v11) * cellH],
            [x0, y0 + interp(v00, v01) * cellH, x0 + interp(v01, v11) * cellW, y1],
          ];
          break;
        case 6:
        case 9:
          segs = [[x0 + interp(v00, v10) * cellW, y0, x0 + interp(v01, v11) * cellW, y1]];
          break;
        case 7:
        case 8:
          segs = [[x0, y0 + interp(v00, v01) * cellH, x0 + interp(v01, v11) * cellW, y1]];
          break;
      }
      
      segments.push(...segs);
    }
  }
  return segments;
}

export default function GexHeatmap({
  frames,
  metric,
  tick = 5,
  onPriceAxisReady,
}: GexHeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState<{ w: number; h: number } | null>(null);
  
  // Resize observer
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDims({ w: Math.floor(width), h: Math.floor(height) });
    });
    ro.observe(el);
    
    return () => ro.disconnect();
  }, []);
  
  // Render heatmap
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !dims || frames.length === 0) return;
    
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    
    const dpr = window.devicePixelRatio || 1;
    canvas.width = dims.w * dpr;
    canvas.height = dims.h * dpr;
    canvas.style.width = `${dims.w}px`;
    canvas.style.height = `${dims.h}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    
    // Layout
    const marginLeft = 60;
    const marginRight = 20;
    const marginTop = 10;
    const marginBottom = 40;
    const plotW = dims.w - marginLeft - marginRight;
    const plotH = dims.h - marginTop - marginBottom;
    
    if (plotW <= 0 || plotH <= 0) return;
    
    // Build shared price axis
    const axis = buildSharedAxis(frames, tick);
    const nT = frames.length;
    const nP = axis.levels.length;
    
    // Notify parent for sync
    if (onPriceAxisReady) {
      onPriceAxisReady(axis);
    }
    
    // Resample all frames
    const grid: number[][] = new Array(nT);
    for (let t = 0; t < nT; t++) {
      grid[t] = resampleFrame(frames[t], axis.levels, metric);
    }
    
    // Aggressive smoothing: temporal then price
    const sigmaTime = 2.5;
    const sigmaPrice = 3.0;
    
    // Temporal smoothing (columns)
    for (let p = 0; p < nP; p++) {
      const col = new Array<number>(nT);
      for (let t = 0; t < nT; t++) col[t] = grid[t][p];
      const smoothed = gaussianSmooth(col, sigmaTime);
      for (let t = 0; t < nT; t++) grid[t][p] = smoothed[t];
    }
    
    // Price smoothing (rows)
    for (let t = 0; t < nT; t++) {
      grid[t] = gaussianSmooth(grid[t], sigmaPrice);
    }
    
    // Symmetric scale: max(|min|, |max|)
    let minVal = Infinity;
    let maxVal = -Infinity;
    for (let t = 0; t < nT; t++) {
      for (let p = 0; p < nP; p++) {
        const v = grid[t][p];
        if (!isNaN(v)) {
          minVal = Math.min(minVal, v);
          maxVal = Math.max(maxVal, v);
        }
      }
    }
    const scale = Math.max(Math.abs(minVal), Math.abs(maxVal));
    
    // Create small offscreen canvas (1 pixel per grid cell)
    const small = document.createElement("canvas");
    small.width = nT;
    small.height = nP;
    const sctx = small.getContext("2d");
    if (!sctx) return;
    
    const imgData = sctx.createImageData(nT, nP);
    const data = imgData.data;
    
    for (let t = 0; t < nT; t++) {
      for (let p = 0; p < nP; p++) {
        const v = grid[t][p];
        const normalized = isNaN(v) ? NaN : v / scale;
        const [r, g, b, a] = colorForValue(normalized);
        
        const idx = (p * nT + t) * 4;
        data[idx] = r;
        data[idx + 1] = g;
        data[idx + 2] = b;
        data[idx + 3] = a;
      }
    }
    
    sctx.putImageData(imgData, 0, 0);
    
    // Clear and draw heatmap (bilinear interpolation)
    ctx.fillStyle = "#000000";
    ctx.fillRect(0, 0, dims.w, dims.h);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(small, marginLeft, marginTop, plotW, plotH);
    
    // Bloom pass (subtle depth glow)
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.filter = "blur(8px)";
    ctx.globalAlpha = 0.15;
    ctx.drawImage(small, marginLeft, marginTop, plotW, plotH);
    ctx.restore();
    
    // Contour lines (marching squares)
    const cellW = plotW / nT;
    const cellH = plotH / nP;
    ctx.save();
    ctx.strokeStyle = "rgba(250, 250, 247, 0.25)";
    ctx.lineWidth = 1;
    
    const contourLevels = [0.2, 0.4, 0.6, 0.8];
    for (const frac of contourLevels) {
      const threshold = frac * scale;
      // Positive contour
      const segsPos = marchingSquares(grid, threshold, cellW, cellH);
      ctx.beginPath();
      for (const [x1, y1, x2, y2] of segsPos) {
        ctx.moveTo(marginLeft + x1, marginTop + y1);
        ctx.lineTo(marginLeft + x2, marginTop + y2);
      }
      ctx.stroke();
      
      // Negative contour
      const segsNeg = marchingSquares(grid, -threshold, cellW, cellH);
      ctx.beginPath();
      for (const [x1, y1, x2, y2] of segsNeg) {
        ctx.moveTo(marginLeft + x1, marginTop + y1);
        ctx.lineTo(marginLeft + x2, marginTop + y2);
      }
      ctx.stroke();
    }
    ctx.restore();
    
    // Forward price line (bone white, prominent)
    ctx.save();
    ctx.strokeStyle = "#FAFAF7";
    ctx.lineWidth = 2.5;
    ctx.shadowColor = "#FAFAF7";
    ctx.shadowBlur = 6;
    ctx.beginPath();
    for (let t = 0; t < nT; t++) {
      const fwd = frames[t].forward;
      const y = marginTop + ((fwd - axis.min) / (axis.max - axis.min)) * plotH;
      const x = marginLeft + (t / (nT - 1)) * plotW;
      if (t === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();
    
    // Aggregate gamma line (sum of gamma around forward ±5 strikes)
    ctx.save();
    ctx.strokeStyle = "#0FB5A8";
    ctx.lineWidth = 2;
    ctx.shadowColor = "#0FB5A8";
    ctx.shadowBlur = 4;
    ctx.beginPath();
    for (let t = 0; t < nT; t++) {
      const fwd = frames[t].forward;
      const window = 5 * tick; // ±5 strikes
      let sum = 0;
      let count = 0;
      
      for (let p = 0; p < nP; p++) {
        const price = axis.levels[p];
        if (Math.abs(price - fwd) <= window) {
          const v = grid[t][p];
          if (!isNaN(v)) {
            sum += v;
            count++;
          }
        }
      }
      
      if (count > 0) {
        const avg = sum / count;
        // Normalize to plot height (scale to ±scale)
        const normalized = avg / scale;
        const y = marginTop + plotH / 2 - (normalized * plotH) / 2;
        const x = marginLeft + (t / (nT - 1)) * plotW;
        if (t === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
    }
    ctx.stroke();
    ctx.restore();
    
    // Axes
    ctx.save();
    ctx.fillStyle = "#6B655B";
    ctx.font = "10px ui-monospace, monospace";
    
    // Y-axis (price)
    const yTicks = 6;
    for (let i = 0; i <= yTicks; i++) {
      const price = axis.min + (i / yTicks) * (axis.max - axis.min);
      const y = marginTop + plotH - (i / yTicks) * plotH;
      ctx.fillText(price.toFixed(0), 10, y + 3);
    }
    
    // X-axis (time)
    const xTicks = 5;
    for (let i = 0; i <= xTicks; i++) {
      const tIdx = Math.floor((i / xTicks) * (nT - 1));
      const frame = frames[tIdx];
      const d = new Date(frame.ts * 1000);
      const hh = d.getUTCHours().toString().padStart(2, "0");
      const mm = d.getUTCMinutes().toString().padStart(2, "0");
      const x = marginLeft + (i / xTicks) * plotW;
      ctx.fillText(`${hh}:${mm}`, x - 18, dims.h - 10);
    }
    ctx.restore();
  }, [dims, frames, metric, tick, onPriceAxisReady]);
  
  return (
    <div ref={containerRef} className="relative h-full w-full">
      <canvas ref={canvasRef} className="absolute inset-0" />
    </div>
  );
}
