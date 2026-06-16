"use client";

/**
 * AsciiEye — large brick-red ASCII disc that "watches" from the hero's
 * right column. Procedurally generated density gradient: sparse outer rim,
 * dense inner core. No iris/pupil — abstract motif that pairs with the
 * brick headline accent rather than a literal eye.
 *
 * Animation: slow opacity pulse (~5s breath cycle), bone-3 → bone-1 →
 * bone-3 modulation via opacity. No per-character animation, no scan,
 * no blink. The disc is a static glyph that breathes.
 *
 * Reduced-motion: opacity locked at the breath midpoint (0.85). No rAF.
 *
 * Render: single <pre>, the frame string is precomputed at module load
 * so React only swaps the wrapper opacity per tick — zero string work
 * after mount.
 */

import { useEffect, useRef, useState } from "react";

// ────────────────────────────────────────────────────────────────────────────
// Disc generation (deterministic, runs once at module load).
// We pick a fixed PRNG seed so the shape is identical between SSR and CSR;
// otherwise hydration would mismatch.

const COLS = 50;
const ROWS = 25;
const CHAR_ASPECT = 0.5; // monospace width/height ratio for circle correction

// Density ramp tuned for visual weight: very thin outer rim, then dense
// fill from ~85% radius inward. Goal is a solid-feeling brick disc, not
// a texture cloud.
const OUTER = [".", ",", "'", "`"];
const MID_OUTER = ["*", "+", "%", "&"];
const MID = ["#", "&", "%", "@"];
const INNER = ["#", "@", "$", "&"];
const CORE = ["#", "@", "$", "█"];

// Mulberry32 PRNG — small, deterministic, browser-safe.
function mulberry32(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function buildDisc(seed: number): string {
  const rnd = mulberry32(seed);
  const cx = COLS / 2;
  const cy = ROWS / 2;
  const radiusRef = Math.max(cx, cy / CHAR_ASPECT);
  const lines: string[] = [];
  for (let y = 0; y < ROWS; y++) {
    let row = "";
    for (let x = 0; x < COLS; x++) {
      const dx = x - cx;
      const dy = (y - cy) / CHAR_ASPECT;
      let r = Math.sqrt(dx * dx + dy * dy) / radiusRef;
      // tiny edge noise so the rim isn't a perfect circle
      r += (rnd() - 0.5) * 0.04;
      let ch = " ";
      if (r > 1.0) ch = " ";
      else if (r > 0.96) ch = OUTER[Math.floor(rnd() * OUTER.length)];
      else if (r > 0.88) ch = MID_OUTER[Math.floor(rnd() * MID_OUTER.length)];
      else if (r > 0.7) ch = MID[Math.floor(rnd() * MID.length)];
      else if (r > 0.45) ch = INNER[Math.floor(rnd() * INNER.length)];
      else ch = CORE[Math.floor(rnd() * CORE.length)];
      row += ch;
    }
    lines.push(row);
  }
  return lines.join("\n");
}

// Precompute the disc once. Seed 7 gives a balanced look in dev.
const DISC_FRAME = buildDisc(7);

// Pulse parameters
const PULSE_PERIOD_MS = 5000; // full breath cycle
const PULSE_MIN = 0.55;
const PULSE_MAX = 1.0;
const STATIC_OPACITY = 0.85;

export function AsciiEye({ className = "" }: { className?: string }) {
  const [opacity, setOpacity] = useState<number>(STATIC_OPACITY);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mq.matches) {
      setOpacity(STATIC_OPACITY);
      return;
    }

    const start = performance.now();
    const tick = (now: number) => {
      const t = ((now - start) % PULSE_PERIOD_MS) / PULSE_PERIOD_MS;
      // Smooth sinusoidal between PULSE_MIN and PULSE_MAX.
      const o = PULSE_MIN + (PULSE_MAX - PULSE_MIN) * (0.5 + 0.5 * Math.sin(t * Math.PI * 2));
      setOpacity(o);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <pre
      aria-hidden="true"
      style={{ opacity }}
      className={`font-mono text-[11px] leading-[0.95] text-brick-glow select-none whitespace-pre tracking-[-0.02em] ${className}`}
    >
      {DISC_FRAME}
    </pre>
  );
}
