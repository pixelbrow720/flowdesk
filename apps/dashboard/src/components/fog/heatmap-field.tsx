"use client";

/**
 * HeatmapField — Canvas2D rendering of GEX field for FOG price-chart background.
 *
 * Implements the pipeline from docs/reference/reverse-engineering-trace-gamma-heatmap.md §3 (Path A — Canvas2D MVP):
 *
 *   1. Field (Float32Array) → ImageData with diverging colormap
 *   2. Upscale + ctx.filter blur → smoothing/glow
 *   3. d3-contour marching-squares → SVG paths (drawn as 2D ctx strokes)
 *   4. Bright-pass copy + heavy blur + additive blend → bloom
 *
 * The component owns *only* the field background + glow + contour. The
 * candle/price/level overlay sits on top in a separate SVG (PriceChart).
 *
 * Color convention (matches FlowDesk brand):
 *   - Negative gamma (short-gamma, dealers amplify vol) → brick/red ramp
 *   - Near-zero (neutral) → near-black ink
 *   - Positive gamma (long-gamma, dealers stabilize)   → turquoise ramp
 *
 * Re-renders only when field reference changes (memoized at parent).
 */

import { useEffect, useRef } from "react";
import { contours as d3contours } from "d3-contour";
import type { GexField } from "@/lib/dummy-field";

type Props = {
  field: GexField;
  width: number; // CSS px
  height: number;
  /** Lo-res render scale: render field at this many px per cell, then upscale. 4 is a good balance. */
  cellPx?: number;
  /** Bloom intensity scalar; 0 = no bloom, 1 = TRACE-like, >1 = blown out. */
  bloomIntensity?: number;
  /** Number of contour iso-bands. */
  contourCount?: number;
  className?: string;
};

// Diverging colormap: negative → brick, 0 → ink, positive → turquoise.
// `t` ∈ [-1, +1].
function colormap(t: number): [number, number, number, number] {
  // Smooth-step magnitude shaping (suppress near-zero noise so neutral stays dark)
  const m = Math.min(Math.abs(t), 1);
  const shaped = m * m * (3 - 2 * m); // smoothstep(0,1,m)

  if (t >= 0) {
    // 0 → ink (#000) → turquoise (#40E0D0)
    const r = 0 + (0x40 - 0) * shaped;
    const g = 0 + (0xe0 - 0) * shaped;
    const b = 0 + (0xd0 - 0) * shaped;
    return [r, g, b, 255 * shaped];
  } else {
    // 0 → ink → brick (#D54452)
    const r = 0 + (0xd5 - 0) * shaped;
    const g = 0 + (0x44 - 0) * shaped;
    const b = 0 + (0x52 - 0) * shaped;
    return [r, g, b, 255 * shaped];
  }
}

export function HeatmapField({
  field,
  width,
  height,
  cellPx = 4,
  bloomIntensity = 0.9,
  contourCount = 8,
  className,
}: Props) {
  const baseRef = useRef<HTMLCanvasElement>(null);
  const bloomRef = useRef<HTMLCanvasElement>(null);
  const contourRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const base = baseRef.current;
    const bloom = bloomRef.current;
    const contour = contourRef.current;
    if (!base || !bloom || !contour) return;

    // ─── 1. Render lo-res ImageData ────────────────────────────────
    const loResW = field.cols;
    const loResH = field.rows;
    const offscreen = document.createElement("canvas");
    offscreen.width = loResW;
    offscreen.height = loResH;
    const offCtx = offscreen.getContext("2d");
    if (!offCtx) return;
    const img = offCtx.createImageData(loResW, loResH);
    for (let i = 0; i < field.values.length; i++) {
      const t = field.values[i] / field.absMax;
      const [r, g, b, a] = colormap(t);
      img.data[i * 4 + 0] = r;
      img.data[i * 4 + 1] = g;
      img.data[i * 4 + 2] = b;
      img.data[i * 4 + 3] = a;
    }
    offCtx.putImageData(img, 0, 0);

    // ─── 2. Upscale + blur to base canvas ──────────────────────────
    base.width = width;
    base.height = height;
    const baseCtx = base.getContext("2d");
    if (!baseCtx) return;
    baseCtx.clearRect(0, 0, width, height);
    baseCtx.imageSmoothingEnabled = true;
    baseCtx.imageSmoothingQuality = "high";
    baseCtx.filter = "blur(6px) saturate(1.05)";
    baseCtx.drawImage(offscreen, 0, 0, width, height);
    baseCtx.filter = "none";

    // ─── 3. Bloom: bright-pass + heavy blur + additive ─────────────
    bloom.width = width;
    bloom.height = height;
    const bloomCtx = bloom.getContext("2d");
    if (!bloomCtx) return;
    bloomCtx.clearRect(0, 0, width, height);
    if (bloomIntensity > 0) {
      // Bright-pass: render field again but only cells with |t| > threshold,
      // saturated to encourage a strong bloom kernel.
      const brightImg = offCtx.createImageData(loResW, loResH);
      const threshold = 0.55; // only top ~45% magnitude contributes to bloom
      for (let i = 0; i < field.values.length; i++) {
        const t = field.values[i] / field.absMax;
        if (Math.abs(t) < threshold) {
          brightImg.data[i * 4 + 3] = 0;
          continue;
        }
        // Saturate beyond cap so bloom looks bright
        const tt = Math.sign(t) * Math.min(1, (Math.abs(t) - threshold) / (1 - threshold) + 0.4);
        const [r, g, b, a] = colormap(tt);
        brightImg.data[i * 4 + 0] = r;
        brightImg.data[i * 4 + 1] = g;
        brightImg.data[i * 4 + 2] = b;
        brightImg.data[i * 4 + 3] = a;
      }
      const brightCanvas = document.createElement("canvas");
      brightCanvas.width = loResW;
      brightCanvas.height = loResH;
      brightCanvas.getContext("2d")!.putImageData(brightImg, 0, 0);

      bloomCtx.globalCompositeOperation = "source-over";
      bloomCtx.filter = `blur(28px) saturate(1.4)`;
      bloomCtx.globalAlpha = bloomIntensity;
      bloomCtx.drawImage(brightCanvas, 0, 0, width, height);
      // Additional softer pass for smoother halo
      bloomCtx.filter = `blur(56px)`;
      bloomCtx.globalAlpha = bloomIntensity * 0.6;
      bloomCtx.drawImage(brightCanvas, 0, 0, width, height);
      bloomCtx.filter = "none";
      bloomCtx.globalAlpha = 1;
    }

    // ─── 4. Contour lines (marching squares via d3-contour) ────────
    contour.width = width;
    contour.height = height;
    const cCtx = contour.getContext("2d");
    if (!cCtx) return;
    cCtx.clearRect(0, 0, width, height);

    // d3-contour wants a flat array of values, plus iso thresholds.
    // We stroke contour lines on absolute magnitude (|γ$|) so both signs
    // contribute to topo-look.
    const absValues = Array.from(field.values, (v) => Math.abs(v));
    const thresholdLevels: number[] = [];
    for (let i = 1; i <= contourCount; i++) {
      thresholdLevels.push((field.absMax * i) / (contourCount + 1));
    }
    const cs = d3contours()
      .size([loResW, loResH])
      .thresholds(thresholdLevels)(absValues);

    const sx = width / loResW;
    const sy = height / loResH;
    cCtx.strokeStyle = "rgba(255,255,255,0.18)";
    cCtx.lineWidth = 0.65;

    for (const c of cs) {
      // c is a MultiPolygon; iterate polygons → rings
      cCtx.beginPath();
      for (const polygon of c.coordinates) {
        for (const ring of polygon) {
          for (let i = 0; i < ring.length; i++) {
            const [x, y] = ring[i];
            const px = x * sx;
            const py = y * sy;
            if (i === 0) cCtx.moveTo(px, py);
            else cCtx.lineTo(px, py);
          }
        }
      }
      cCtx.stroke();
    }
  }, [field, width, height, cellPx, bloomIntensity, contourCount]);

  return (
    <div className={className} style={{ position: "relative", width, height }}>
      <canvas
        ref={baseRef}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
        }}
      />
      <canvas
        ref={bloomRef}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          mixBlendMode: "screen",
          pointerEvents: "none",
        }}
      />
      <canvas
        ref={contourRef}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          pointerEvents: "none",
        }}
      />
    </div>
  );
}

export default HeatmapField;
