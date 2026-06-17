"use client";

import { useEffect, useRef, useState } from "react";
import { createGLHeatmap } from "./glHeatmap";
import type { GLHeatmapHandle } from "./glHeatmap";

// Dynamic price-band half-width (points) around the median forward. The fog
// grid drifts frame-to-frame, so a union axis leaves large NaN regions whose
// moving coverage edge draws hard vertical streaks. Clamping to a tight band
// around the forward + edge-extrapolation kills the banding. Verified in
// HANDOFF.md — do not widen back to a union range.
const PRICE_BAND_PT = 180;

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

// Build the shared price axis as a tight band clamped to the MEDIAN forward
// ±PRICE_BAND_PT, snapped to tick. Using the median (not per-frame forward)
// keeps the axis stable for the whole session so the heatmap doesn't scroll
// vertically. Returns levels DESCENDING (high → low) so p=0 maps to the TOP of
// the canvas — matching the right-axis labels and the left-hand price ladder.
function buildSharedAxis(frames: HeatmapFrame[], tick: number) {
  const forwards = frames
    .map((f) => f.forward)
    .filter((v) => Number.isFinite(v))
    .sort((a, b) => a - b);
  const median =
    forwards.length > 0 ? forwards[Math.floor(forwards.length / 2)] : 0;

  let min = Math.floor((median - PRICE_BAND_PT) / tick) * tick;
  let max = Math.ceil((median + PRICE_BAND_PT) / tick) * tick;
  // Degenerate guard (no frames): keep a non-empty axis.
  if (!(max > min)) {
    min = 0;
    max = tick;
  }

  const levels: number[] = [];
  for (let p = max; p >= min; p -= tick) {
    levels.push(p);
  }
  return { min, max, levels };
}

// Resample a frame's metric onto the shared axis with linear interpolation
// INSIDE the frame's own price_grid coverage, and EDGE-HOLD (clamp to the
// nearest edge value) outside it. Holding the edge instead of writing NaN is
// what removes the vertical banding at the moving coverage edge.
function resampleFrame(
  frame: HeatmapFrame,
  axisLevels: number[],
  metric: "gamma" | "delta"
): number[] {
  const result = new Array<number>(axisLevels.length);
  const src = metric === "gamma" ? frame.gamma : frame.delta;
  const srcPrices = frame.price_grid;

  if (srcPrices.length === 0) {
    result.fill(0);
    return result;
  }
  const loEdge = srcPrices[0];
  const hiEdge = srcPrices[srcPrices.length - 1];

  for (let i = 0; i < axisLevels.length; i++) {
    const target = axisLevels[i];
    if (target <= loEdge) {
      result[i] = src[0];
      continue;
    }
    if (target >= hiEdge) {
      result[i] = src[src.length - 1];
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
  const glCanvasRef = useRef<HTMLCanvasElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const crosshairRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const glHandleRef = useRef<GLHeatmapHandle | null>(null);
  const [dims, setDims] = useState<{ w: number; h: number } | null>(null);
  // Layout + data snapshot shared with the crosshair overlay so it can map
  // pointer position → price / time without re-running the heavy heatmap render.
  const layoutRef = useRef<{
    marginLeft: number;
    marginTop: number;
    plotW: number;
    plotH: number;
    axisMin: number;
    axisMax: number;
    ts: number[];
  } | null>(null);
  
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

  // Initialise the WebGL heatmap renderer once (per mounted canvas).
  useEffect(() => {
    const gl = glCanvasRef.current;
    if (!gl) return;
    const handle = createGLHeatmap(gl);
    glHandleRef.current = handle;
    return () => {
      handle?.destroy();
      glHandleRef.current = null;
    };
  }, []);

  // Render heatmap. WebGL paints the GEX/DEX field (smooth + bloom) into the
  // plot rect; this Canvas2D layer is transparent and only carries the
  // overlays (contours, candles, gamma line, axes).
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
    
    // Layout — price axis labels live on the RIGHT side of the plot.
    const marginLeft = 12;
    const marginRight = 58;
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
    
    // Resample all frames onto the clamped axis (edge-hold, no NaN).
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
    const scale = Math.max(Math.abs(minVal), Math.abs(maxVal)) || 1;
    
    // Upload the normalized field to the GPU and render (smooth + bloom).
    // Field is row-major (p*nT + t); row 0 = highest price = top of plot.
    const field = new Float32Array(nT * nP);
    for (let t = 0; t < nT; t++) {
      for (let p = 0; p < nP; p++) {
        field[p * nT + t] = grid[t][p] / scale;
      }
    }
    const glDpr = window.devicePixelRatio || 1;
    const glCanvas = glCanvasRef.current;
    if (glCanvas) {
      glCanvas.width = dims.w * glDpr;
      glCanvas.height = dims.h * glDpr;
      glCanvas.style.width = `${dims.w}px`;
      glCanvas.style.height = `${dims.h}px`;
    }
    glHandleRef.current?.render(
      { nT, nP, data: field },
      { left: marginLeft, top: marginTop, width: plotW, height: plotH },
      glDpr,
    );
    
    // The 2D layer is transparent over the WebGL canvas; only overlays below.
    ctx.clearRect(0, 0, dims.w, dims.h);
    
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
    
// Candlesticks from the forward path, aggregated to reduce noise.
// 0DTE options snapshots carry no intraday futures OHLC (`ohlc` is null),
// so candles are built from the per-minute forward series grouped into
// buckets of `candleBucket`: open=first, high=max, low=min, close=last.
// Up (close >= open): bone-white body. Down: black body. Border: bone white.
const candleBucket = 5;
const nCandles = Math.ceil(nT / candleBucket);
const candles: Array<{ open: number; high: number; low: number; close: number; tMid: number }> = [];
for (let i = 0; i < nCandles; i++) {
  const start = i * candleBucket;
  const end = Math.min(start + candleBucket, nT);
  const open = frames[start].forward;
  const close = frames[end - 1].forward;
  let high = -Infinity;
  let low = Infinity;
  for (let t = start; t < end; t++) {
    high = Math.max(high, frames[t].forward);
    low = Math.min(low, frames[t].forward);
  }
  candles.push({ open, high, low, close, tMid: start + (end - start - 1) / 2 });
}
const slotW = plotW / nCandles;
const bodyW = Math.max(1.5, slotW * 0.65);
const yForPrice = (price: number) =>
  marginTop + ((axis.max - price) / (axis.max - axis.min)) * plotH;
ctx.save();
ctx.lineWidth = 1;
for (let i = 0; i < nCandles; i++) {
  const c = candles[i];
  const up = c.close >= c.open;
  const x = marginLeft + ((i + 0.5) / nCandles) * plotW;
  const yOpen = yForPrice(c.open);
  const yClose = yForPrice(c.close);
  const yHigh = yForPrice(c.high);
  const yLow = yForPrice(c.low);
  const top = Math.min(yOpen, yClose);
  const h = Math.max(1, Math.abs(yClose - yOpen));
  // Wick (thin line from high to low)
  ctx.strokeStyle = "#FAFAF7";
  ctx.beginPath();
  ctx.moveTo(x, yHigh);
  ctx.lineTo(x, yLow);
  ctx.stroke();
  // Body
  ctx.fillStyle = up ? "#FAFAF7" : "#000000";
  ctx.fillRect(x - bodyW / 2, top, bodyW, h);
  ctx.strokeStyle = "#FAFAF7";
  ctx.strokeRect(x - bodyW / 2, top, bodyW, h);
}
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
    
    // Y-axis (price) — labels on the RIGHT of the plot.
    const yTicks = 6;
    ctx.textAlign = "left";
    for (let i = 0; i <= yTicks; i++) {
      const price = axis.min + (i / yTicks) * (axis.max - axis.min);
      const y = marginTop + plotH - (i / yTicks) * plotH;
      ctx.fillText(price.toFixed(0), marginLeft + plotW + 8, y + 3);
    }
    ctx.textAlign = "start";
    
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

    // Publish layout for the crosshair overlay.
    layoutRef.current = {
      marginLeft,
      marginTop,
      plotW,
      plotH,
      axisMin: axis.min,
      axisMax: axis.max,
      ts: frames.map((f) => f.ts),
    };
  }, [dims, frames, metric, tick, onPriceAxisReady]);
  
  // Crosshair overlay — drawn on a separate canvas so pointer moves never
  // trigger the heavy heatmap re-render. Maps pointer → price (right axis)
  // and time (bottom axis), with a dashed cross and value labels.
  useEffect(() => {
    const cv = crosshairRef.current;
    const container = containerRef.current;
    if (!cv || !container || !dims) return;

    const dpr = window.devicePixelRatio || 1;
    cv.width = dims.w * dpr;
    cv.height = dims.h * dpr;
    cv.style.width = `${dims.w}px`;
    cv.style.height = `${dims.h}px`;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const clear = () => ctx.clearRect(0, 0, dims.w, dims.h);

    const draw = (mx: number, my: number) => {
      const L = layoutRef.current;
      if (!L) return;
      clear();
      const { marginLeft, marginTop, plotW, plotH, axisMin, axisMax, ts } = L;
      // Only inside the plot area.
      if (mx < marginLeft || mx > marginLeft + plotW || my < marginTop || my > marginTop + plotH) {
        return;
      }
      ctx.save();
      ctx.strokeStyle = "rgba(250, 250, 247, 0.55)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      // Vertical
      ctx.beginPath();
      ctx.moveTo(mx, marginTop);
      ctx.lineTo(mx, marginTop + plotH);
      ctx.stroke();
      // Horizontal
      ctx.beginPath();
      ctx.moveTo(marginLeft, my);
      ctx.lineTo(marginLeft + plotW, my);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.font = "10px ui-monospace, monospace";
      // Price label (right axis): top = axisMax, bottom = axisMin.
      const price = axisMax - ((my - marginTop) / plotH) * (axisMax - axisMin);
      const priceTxt = price.toFixed(1);
      ctx.fillStyle = "#FAFAF7";
      ctx.fillRect(marginLeft + plotW + 2, my - 7, 48, 14);
      ctx.fillStyle = "#000000";
      ctx.textAlign = "left";
      ctx.fillText(priceTxt, marginLeft + plotW + 6, my + 3);

      // Time label (bottom axis).
      const frac = (mx - marginLeft) / plotW;
      const idx = Math.round(frac * (ts.length - 1));
      const d = new Date(ts[Math.max(0, Math.min(ts.length - 1, idx))] * 1000);
      const hh = d.getUTCHours().toString().padStart(2, "0");
      const mm = d.getUTCMinutes().toString().padStart(2, "0");
      const timeTxt = `${hh}:${mm}`;
      const tw = ctx.measureText(timeTxt).width + 8;
      ctx.fillStyle = "#FAFAF7";
      ctx.fillRect(mx - tw / 2, marginTop + plotH + 4, tw, 14);
      ctx.fillStyle = "#000000";
      ctx.textAlign = "center";
      ctx.fillText(timeTxt, mx, marginTop + plotH + 14);
      ctx.restore();
    };

    const onMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      draw(e.clientX - rect.left, e.clientY - rect.top);
    };
    const onLeave = () => clear();

    container.addEventListener("mousemove", onMove);
    container.addEventListener("mouseleave", onLeave);
    return () => {
      container.removeEventListener("mousemove", onMove);
      container.removeEventListener("mouseleave", onLeave);
    };
  }, [dims, frames]);

  return (
    <div ref={containerRef} className="relative h-full w-full">
      {/* Stack: WebGL field (bottom) → Canvas2D overlay (contour/candles/axis)
          → crosshair (top). */}
      <canvas ref={glCanvasRef} className="absolute inset-0" />
      <canvas ref={canvasRef} className="pointer-events-none absolute inset-0" />
      <canvas ref={crosshairRef} className="pointer-events-none absolute inset-0" />
    </div>
  );
}
